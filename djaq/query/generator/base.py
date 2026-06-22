"""SQL generation: walk a ResolvedQuery and emit ``(sql, params)``.

``SQLGenerator`` owns the tree traversal and the dialect-neutral clause
assembly. ``Dialect`` is a thin strategy object holding only the vendor-specific
decisions (identifier quoting, function rendering, LIMIT/OFFSET, date parts,
casts). This keeps one generator and N small dialects.
"""

from django.db.models.fields.related import ManyToOneRel

from .. import ir


JOIN_OPERATORS = {"->": "LEFT JOIN", "<-": "RIGHT JOIN", "<>": "INNER JOIN"}

ARITHMETIC = {ir.Op.ADD, ir.Op.SUB, ir.Op.MUL, ir.Op.DIV}


class Dialect:
    """Vendor-specific rendering decisions. Subclassed per database."""

    name = "generic"

    # --- identifiers --------------------------------------------------------
    def quote_ident(self, ident: str) -> str:
        return f'"{ident}"'

    def quote_table(self, table: str) -> str:
        return f'"{table}"'

    # --- parameters ---------------------------------------------------------
    def placeholder(self, name: str) -> str:
        # Named placeholder (current behaviour). Positional binding arrives with
        # the SQLite dialect, which needs it to expand IN-lists.
        return f"%({name})s"

    # --- clauses with vendor quirks ----------------------------------------
    def limit_offset(self, limit, offset) -> str:
        # A falsy limit/offset (0 or None) means "unset" -- matches the historical
        # behaviour where the API defaults page_size to 0 to mean "no limit".
        out = ""
        if limit:
            out += f" LIMIT {int(limit)}"
        if offset:
            out += f" OFFSET {int(offset)}"
        return out

    def date_extract(self, part: str, expr_sql: str) -> str:
        if part.lower() == "date":
            return f"DATE({expr_sql})"
        return f"date_part('{part}', {expr_sql})"

    def cast(self, expr_sql: str, type_sql: str) -> str:
        t = type_sql.replace("'", "")
        return f"{expr_sql}::{t}"

    # --- functions ----------------------------------------------------------
    #: name -> (dialect, rendered_args) -> sql. Base provides the portable
    #: templates; dialects override the non-portable ones.
    @property
    def functions(self):
        return {
            "iif": lambda d, a: f"CASE WHEN {a[0]} THEN {a[1]} ELSE {a[2]} END",
            "like": lambda d, a: f"{a[0]} LIKE {a[1]}",
            "ilike": lambda d, a: f"{a[0]} ILIKE {a[1]}",
            "regex": lambda d, a: f"{a[0]} ~ {a[1]}",
            "concat": lambda d, a: " || ".join(a),
            "cast": lambda d, a: d.cast(a[0], a[1]),
            "today": lambda d, a: "CURRENT_DATE",
            "pointx": lambda d, a: f"ST_X({a[0]})",
            "pointy": lambda d, a: f"ST_Y({a[0]})",
            "countdistinct": lambda d, a: f"COUNT(DISTINCT {a[0]})",
            "sumif": lambda d, a: f"SUM(CASE WHEN {a[0]} THEN {a[1]} ELSE {a[2]} END)",
            "index_choice0": _index_choice0,
        }

    def render_function(self, name: str, args: list) -> str:
        fn = self.functions.get(name)
        if fn is not None:
            return fn(self, args)
        return f"{name.upper()}({', '.join(args)})"


def _index_choice0(dialect, args):
    args = list(args)
    index = args.pop(0)
    s = f"CASE {index} "
    for i, a in enumerate(args):
        s += f"WHEN {i} THEN {a} "
    return s + "END"


class SQLGenerator:
    def __init__(self, dialect: Dialect, named_resolver=None):
        self.d = dialect
        # callback: name -> (sql, params) for @named references; injected at wiring
        self.named_resolver = named_resolver

    # ------------------------------------------------------------------ query
    def generate(self, q: ir.ResolvedQuery):
        self.params: list = []
        root = q.relations[0]

        select = ", ".join(self.render(p.expr) for p in q.projections)
        keyword = "SELECT DISTINCT" if q.distinct else "SELECT"
        sql = f"{keyword} {select} FROM {root.table}"

        for rel in q.relations[1:]:
            op = JOIN_OPERATORS.get(rel.join_type, "LEFT JOIN")
            on = self._join_on(rel)
            sql += f" {op} {rel.table} {rel.alias or ''} ON {on}"

        if q.where is not None:
            sql += f" WHERE {self.render(q.where)}"

        if q.group_by:
            sql += " GROUP BY " + ", ".join(self.render(e) for e in q.group_by)

        if q.order_by:
            terms = [f"{self.render(o.expr)} {o.direction.value}" for o in q.order_by]
            sql += " ORDER BY " + ", ".join(terms)

        sql += self.d.limit_offset(q.limit, q.offset)
        return sql, self.params

    # ------------------------------------------------------------------ joins
    def _join_on(self, rel: ir.Relation) -> str:
        jf = rel.join_field
        qt, qi = self.d.quote_table, self.d.quote_ident
        parts = []
        if hasattr(jf, "related_fields"):
            for fk, f in jf.related_fields:
                parts.append(
                    f"{qt(fk.model._meta.db_table)}.{qi(fk.column)} = "
                    f"{qt(f.model._meta.db_table)}.{qi(f.column)}"
                )
        elif isinstance(jf, ManyToOneRel):
            left = rel.alias or jf.model._meta.db_table
            for f_from, f_to in jf.get_joining_columns():
                parts.append(
                    f"{qt(left)}.{qi(f_from)} = "
                    f"{qt(jf.related_model._meta.db_table)}.{qi(f_to)}"
                )
        else:
            raise Exception(f"Cannot derive join condition from {jf!r}")
        return "(" + " AND ".join(parts) + ")"

    # ------------------------------------------------------------ expressions
    def render(self, e: ir.Expr) -> str:
        if isinstance(e, ir.FieldRef):
            return f"{self.d.quote_table(e.relation.ref)}.{self.d.quote_ident(e.column)}"

        if isinstance(e, ir.Literal):
            return self._literal(e.value)

        if isinstance(e, ir.Param):
            return self.d.placeholder(e.name)

        if isinstance(e, ir.DateExtract):
            return self.d.date_extract(e.part, self.render(e.source))

        if isinstance(e, ir.Case):
            whens = " ".join(
                f"WHEN ({self.render(c)}) THEN {self.render(r)}" for c, r in e.whens
            )
            default = f" ELSE {self.render(e.default)}" if e.default is not None else ""
            return f"CASE {whens}{default} END"

        if isinstance(e, ir.BinaryOp):
            left, right = self.render(e.left), self.render(e.right)
            if e.op in ARITHMETIC:
                return f"({left} {e.op.value} {right})"
            return f"{left} {e.op.value} {right}"

        if isinstance(e, ir.BoolOp):
            joiner = f" {e.kind.value} "
            return "(" + joiner.join(self.render(o) for o in e.operands) + ")"

        if isinstance(e, ir.Not):
            return f"NOT {self.render(e.operand)}"

        if isinstance(e, ir.Unary):
            return f"{e.op.value}{self.render(e.operand)}"

        if isinstance(e, ir.Func):
            return self.d.render_function(e.name, [self.render(a) for a in e.args])

        if isinstance(e, ir.TupleExpr):
            return "(" + ", ".join(self.render(el) for el in e.elements) + ")"

        if isinstance(e, ir.RawSQL):
            self.params.extend(e.params)
            return f"({e.sql})"

        if isinstance(e, ir.NamedRef):
            if not self.named_resolver:
                raise Exception(f"No resolver for named reference @{e.name}")
            sql, params = self.named_resolver(e.name)
            self.params.extend(params)
            return f"({sql})"

        raise TypeError(f"Cannot render IR node: {type(e).__name__}")

    def _literal(self, value) -> str:
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if value is None:
            return "NULL"
        if isinstance(value, str):
            return "'" + value + "'"
        return str(value)
