"""Resolver: bind an unresolved :class:`~djaq.query.ir.Query` to the schema.

This is the only part of the pipeline that touches Django model metadata. It
walks the IR produced by the frontend and:

* replaces every :class:`~djaq.query.ir.Name` with a concrete
  :class:`~djaq.query.ir.FieldRef` (or a ``DateExtract``/``Case`` rewrite),
  building the join graph (:class:`~djaq.query.ir.Relation`) as it goes;
* classifies each :class:`~djaq.query.ir.Func` as aggregate or scalar
  (validating it against the function catalogues / whitelist);
* computes the ``GROUP BY`` keys.

The name-resolution logic is a faithful port of the old
``ExpressionParser.push_attribute_relations`` / ``add_relation``, but it returns
IR nodes and builds ``Relation`` graph nodes instead of emitting SQL strings.
"""

from django.db.models.fields.related import ManyToManyField, OneToOneRel

from ..app_utils import (
    find_model_class,
    get_field_from_model,
    get_model_from_table,
    model_path,
)
from ..exceptions import UnknownFunctionException
from .sql_functions import func_in_whitelist
from . import ir


class Resolver:
    def __init__(self, model, whitelist=None):
        self.model = model
        self.whitelist = whitelist
        self.relations: list[ir.Relation] = []
        self._add_relation(model)

    # ------------------------------------------------------------------ joins
    def _add_relation(
        self, model, parent=None, join_field=None, alias=None, field_name=None
    ) -> ir.Relation:
        """Add a relation to the graph, de-duplicating by model (and alias)."""
        for relation in self.relations:
            if model_path(relation.model) == model_path(model):
                if alias and relation.alias:
                    if alias == relation.alias:
                        return relation
                    # different aliases -> fall through and create a new one
                else:
                    if alias:
                        relation.alias = alias
                    return relation

        relation = ir.Relation(
            model=model, alias=alias, parent=parent, join_field=join_field
        )
        self.relations.append(relation)

        if len(self.relations) > 1 and not relation.join_field:
            # discover how this relation joins to an existing one
            for rel in self.relations:
                for f in rel.model._meta.get_fields():
                    if f.related_model == relation.model:
                        # there can be several fields to this model; pick the
                        # one named by field_name if given
                        if field_name and not f.name == field_name:
                            continue
                        relation.parent = rel
                        relation.join_field = f
                        break
                if relation.parent:
                    break
        return relation

    # --------------------------------------------------------------- names
    def _date_attribute(self, field, relation, remaining) -> ir.Expr:
        """Resolve a date/datetime part access, e.g. ``pubdate.year``."""
        part = remaining.pop()
        source = ir.FieldRef(relation, field.column, field)
        internal = field.get_internal_type()
        if internal == "DateTimeField" and part.lower() == "date":
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

    def resolve_path(self, path, relation=None) -> ir.Expr:
        """Port of ``push_attribute_relations``; returns an IR expression.

        ``path`` is in natural order and consumed front-to-back: the leading
        element is the relation closest to the root, the trailing element is the
        terminal attribute. ``publisher.owner.name`` -> ``("publisher","owner","name")``.
        """
        path = list(path)
        try:
            attr = path.pop(0)
        except IndexError:
            if not relation:
                relation = self._add_relation(self.model)
            return self.resolve_path(path, relation)

        # terminal attribute on a known relation
        if relation and not path:
            if attr.endswith("_display"):
                field = relation.model._meta.get_field(attr[:-8])
                if field.choices:
                    return self._display_case(field, relation)
            field = relation.model._meta.get_field(attr)
            if isinstance(field, OneToOneRel):
                raise Exception("Specify a field name in the related model")
            return ir.FieldRef(relation, field.column, field)

        # stand-alone name on the root relation
        if not relation and not path:
            if not self.relations:
                self._add_relation(self.model)
            model = self.relations[0].model
            if attr.endswith("_display"):
                field = model._meta.get_field(attr[:-8])
            else:
                field = model._meta.get_field(attr)
            if field.auto_created and not field.concrete:
                # reverse relation to an FK in another model (e.g. count(book))
                rel = self._add_relation(field.related_model)
                return ir.FieldRef(rel, field.get_joining_columns()[0][1], None)
            if attr.endswith("_display") and field.choices:
                return self._display_case(field, self.relations[0])
            return ir.FieldRef(self.relations[0], field.column, field)

        # a relation step (FK / M2M / date-attr) with more path to follow
        relation = relation or self.relations[0]
        field = relation.model._meta.get_field(attr)

        if isinstance(field, ManyToManyField):
            link_model = get_model_from_table(field.m2m_db_table())
            link_fk = get_field_from_model(link_model, field.m2m_field_name())
            self._add_relation(link_model, parent=relation, join_field=link_fk)
            reverse_fk = get_field_from_model(
                link_model, field.m2m_reverse_field_name()
            )
            terminal = path.pop(0)
            self._add_relation(field.related_model, join_field=reverse_fk)
            related_field = get_field_from_model(field.related_model, terminal)
            # find the relation we just added for the related model
            target = self.relations[-1]
            return ir.FieldRef(target, related_field.column, related_field)

        related_model = field.related_model
        if related_model:
            # FK / O2O: check whitelist, then add the join and recurse
            find_model_class(related_model._meta.label, whitelist=self.whitelist)
            new_relation = self._add_relation(related_model, field_name=attr)
            return self.resolve_path(path, new_relation)

        # not a relation: a scalar field with a trailing attribute -> date part
        return self._date_attribute(field, relation, path)

    # ----------------------------------------------------------- expressions
    def resolve_expr(self, node: ir.Expr) -> ir.Expr:
        if isinstance(node, ir.Name):
            return self.resolve_path(node.path)
        if isinstance(node, (ir.Literal, ir.Param, ir.RawSQL)):
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
        if isinstance(node, ir.Subquery):
            return node  # nested queries are resolved by the frontend
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
