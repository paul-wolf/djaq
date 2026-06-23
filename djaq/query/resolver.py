"""Resolver: bind an unresolved :class:`~djaq.query.ir.Query` to a schema.

Given a schema provider (something with ``get_entity(label) -> schema.Entity``)
and a root entity label, the resolver walks the IR and:

* replaces every :class:`~djaq.query.ir.Name` with a concrete
  :class:`~djaq.query.ir.FieldRef` (or a ``DateExtract``/``Case`` rewrite),
  building the join graph (:class:`~djaq.query.ir.Relation` carrying precomputed
  ``schema.JoinKey`` keys) as it goes;
* classifies each :class:`~djaq.query.ir.Func` as aggregate or scalar;
* computes the ``GROUP BY`` keys.

It imports no Django: it depends only on the schema contract and the provider
interface. The provider (e.g. ``DjangoSchemaProvider``) is the only ORM-coupled
piece, and its ``get_entity`` is also where the whitelist is enforced.
"""

from ..exceptions import UnknownFunctionException
from .sql_functions import func_in_whitelist
from . import ir


class Resolver:
    def __init__(self, provider, root_label):
        self.provider = provider
        self._alias_n = 0
        root = provider.get_entity(root_label)
        self.relations: list[ir.Relation] = [
            ir.Relation(table=root.table, entity=root, path=())
        ]

    # ------------------------------------------------------------------ joins
    def _alias_for(self, table) -> str:
        """An alias if ``table`` is already in the graph (so a self/duplicate join
        stays distinct), else None."""
        if any(r.table == table for r in self.relations):
            self._alias_n += 1
            return f"t{self._alias_n}"
        return None

    def _join_pairs(self, parent, new_table, keys):
        """Orient each schema JoinKey into ``(parent_column, this_column)``.

        When ``parent`` and the new relation share a table (self-referential
        single hop), the provider puts the source (parent) on the left and the
        target (new) on the right; otherwise we match each side by table name.
        """
        pairs = []
        for k in keys:
            if parent.table == new_table:
                pairs.append((k.left_column, k.right_column))
            elif k.left_table == new_table and k.right_table == parent.table:
                pairs.append((k.right_column, k.left_column))
            elif k.right_table == new_table and k.left_table == parent.table:
                pairs.append((k.left_column, k.right_column))
            else:
                raise Exception(f"cannot orient join key {k} for {parent.table}->{new_table}")
        return tuple(pairs)

    def _traverse(self, parent, path, entity, table, keys) -> ir.Relation:
        """Add (or reuse by ``path``) a relation joined to ``parent``."""
        for r in self.relations:
            if r.path == path:
                return r
        rel = ir.Relation(
            table=table,
            entity=entity,
            alias=self._alias_for(table),
            parent=parent,
            join_pairs=self._join_pairs(parent, table, keys),
            path=path,
        )
        self.relations.append(rel)
        return rel

    # --------------------------------------------------------------- names
    def _date_attribute(self, field, relation, remaining) -> ir.Expr:
        """Resolve a date/datetime part access, e.g. ``pubdate.year``."""
        part = remaining.pop(0)
        source = ir.FieldRef(relation, field.column, field)
        if field.type == "datetime" and part.lower() == "date":
            return ir.DateExtract("date", source)
        return ir.DateExtract(part, source)

    def _display_case(self, field, relation) -> ir.Expr:
        """Rewrite a ``*_display`` choice field into a CASE expression."""
        source = ir.FieldRef(relation, field.column, field)
        whens = tuple(
            (ir.BinaryOp(ir.Op.EQ, source, ir.Literal(k)), ir.Literal(v))
            for k, v in field.choices
        )
        return ir.Case(whens=whens)

    def _terminal(self, relation, attr) -> ir.Expr:
        entity = relation.entity
        if attr.endswith("_display"):
            base = entity.field(attr[:-8])
            if base and base.choices:
                return self._display_case(base, relation)
        field = entity.field(attr)
        if field:
            return ir.FieldRef(relation, field.column, field)
        if entity.relation(attr):
            raise Exception("Specify a field name in the related model")
        raise Exception(f"Unknown field: {entity.name}.{attr}")

    def _standalone(self, attr) -> ir.Expr:
        root = self.relations[0]
        entity = root.entity
        base_name = attr[:-8] if attr.endswith("_display") else attr
        field = entity.field(base_name)
        if field:
            if attr.endswith("_display") and field.choices:
                return self._display_case(field, root)
            return ir.FieldRef(root, field.column, field)
        rel = entity.relation(attr)
        if rel and rel.kind == "reverse":
            # a reverse relation used as a value, e.g. count(book)
            target_entity = self.provider.get_entity(rel.target)
            target = self._traverse(
                root, (attr,), target_entity, target_entity.table, rel.keys
            )
            return ir.FieldRef(target, rel.keys[0].right_column, None)
        raise Exception(f"Unknown name: {entity.name}.{attr}")

    def resolve_path(self, path, relation=None) -> ir.Expr:
        """Resolve a dotted name to an IR expression (front-to-back).

        ``publisher.owner.name`` -> ``("publisher","owner","name")``: leading
        elements are relations to traverse, the trailing element is terminal.
        """
        path = list(path)
        try:
            attr = path.pop(0)
        except IndexError:
            return self._terminal(relation or self.relations[0], attr)

        if relation and not path:
            return self._terminal(relation, attr)
        if not relation and not path:
            return self._standalone(attr)

        # a relation step with more path to follow
        relation = relation or self.relations[0]
        entity = relation.entity
        rel = entity.relation(attr)

        if rel and rel.kind == "m2m":
            base = relation.path + (attr,)
            link = self._traverse(
                relation, base + ("__link",), None, rel.link_table, rel.link_keys
            )
            target_entity = self.provider.get_entity(rel.target)
            target = self._traverse(
                link, base, target_entity, target_entity.table, rel.keys
            )
            terminal = path.pop(0)
            field = target_entity.field(terminal)
            return ir.FieldRef(target, field.column, field)

        if rel:
            target_entity = self.provider.get_entity(rel.target)  # whitelist enforced
            new_relation = self._traverse(
                relation,
                relation.path + (attr,),
                target_entity,
                target_entity.table,
                rel.keys,
            )
            return self.resolve_path(path, new_relation)

        # not a relation: a scalar field with a trailing attribute -> date part
        field = entity.field(attr)
        return self._date_attribute(field, relation, path)

    # ----------------------------------------------------------- expressions
    def resolve_expr(self, node: ir.Expr) -> ir.Expr:
        if isinstance(node, ir.Name):
            return self.resolve_path(node.path)
        if isinstance(node, (ir.Literal, ir.Param, ir.RawSQL, ir.NamedRef)):
            return node
        if isinstance(node, ir.BinaryOp):
            return ir.BinaryOp(
                node.op, self.resolve_expr(node.left), self.resolve_expr(node.right)
            )
        if isinstance(node, ir.BoolOp):
            return ir.BoolOp(
                node.kind, tuple(self.resolve_expr(o) for o in node.operands)
            )
        if isinstance(node, ir.Not):
            return ir.Not(self.resolve_expr(node.operand))
        if isinstance(node, ir.Unary):
            return ir.Unary(node.op, self.resolve_expr(node.operand))
        if isinstance(node, ir.TupleExpr):
            return ir.TupleExpr(tuple(self.resolve_expr(e) for e in node.elements))
        if isinstance(node, ir.Func):
            return self.resolve_func(node)
        # already-resolved nodes pass through
        return node

    def resolve_func(self, node: ir.Func) -> ir.Func:
        args = tuple(self.resolve_expr(a) for a in node.args)
        name = node.name.lower()
        if name in ir.AGGREGATE_FUNCS:
            kind = ir.FuncKind.AGGREGATE
        elif name in ir.TEMPLATE_FUNCS or func_in_whitelist(name):
            kind = ir.FuncKind.SCALAR
        else:
            raise UnknownFunctionException(f"Function '{name}' not known")
        return ir.Func(name, args, kind)

    # --------------------------------------------------------------- query
    def resolve(self, query: ir.Query) -> ir.ResolvedQuery:
        projections = [
            ir.Projection(self.resolve_expr(p.expr), p.alias)
            for p in query.projections
        ]
        where = self.resolve_expr(query.where) if query.where is not None else None
        order_by = [
            ir.Order(self.resolve_expr(o.expr), o.direction) for o in query.order_by
        ]

        group_by: list[ir.Expr] = []
        if any(ir.contains_aggregate(p.expr) for p in projections):
            group_by = [
                p.expr for p in projections if not ir.contains_aggregate(p.expr)
            ]

        return ir.ResolvedQuery(
            model=query.model,
            projections=projections,
            where=where,
            order_by=order_by,
            limit=query.limit,
            offset=query.offset,
            distinct=query.distinct,
            local=query.local,
            relations=self.relations,
            group_by=group_by,
        )
