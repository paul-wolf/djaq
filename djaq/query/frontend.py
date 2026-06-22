"""Frontend: Djaq source text -> unresolved :class:`~djaq.query.ir.Query`.

This is structural only: it produces IR nodes and performs no model lookups and
no SQL generation. It currently reuses Python's ``ast`` to parse expressions
(the historical approach); Phase 3 replaces this with a hand-written parser that
emits the same IR, leaving the resolver and generator untouched.
"""

import ast
import re

from django.utils.text import slugify

from . import ir


_JOIN_SPLIT = re.compile(r"->|<-|<>")

# ast operator class -> IR Op
_BINOP = {
    ast.Add: ir.Op.ADD,
    ast.Sub: ir.Op.SUB,
    ast.Mult: ir.Op.MUL,
    ast.Div: ir.Op.DIV,
}
_CMPOP = {
    ast.Gt: ir.Op.GT,
    ast.Lt: ir.Op.LT,
    ast.Eq: ir.Op.EQ,
    ast.NotEq: ir.Op.NE,
    ast.LtE: ir.Op.LE,
    ast.GtE: ir.Op.GE,
    ast.Is: ir.Op.IS,
    ast.IsNot: ir.Op.IS_NOT,
    ast.In: ir.Op.IN,
    ast.NotIn: ir.Op.NOT_IN,
}


# --------------------------------------------------------------------------
# Column-list splitting (respects parentheses and the ``as`` alias syntax)
# --------------------------------------------------------------------------
def split_columns(s):
    """Yield top-level comma-separated column expressions from ``s``."""
    depth = 0
    col = ""
    for c in s:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and not depth:
            yield col.strip()
            col = ""
        else:
            col += c
    if col.strip():
        yield col.strip()


def parse_column_aliases(select_src):
    """Return ``[(expr_str, alias), ...]`` for a select source."""
    s = select_src.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    aliases = []
    for col in split_columns(s):
        parts = col.split(" as ")
        if len(parts) == 1:
            slug = slugify(parts[0].replace(".", "_").replace(" ", "_")).replace(
                "-", "_"
            )
            aliases.append((parts[0].strip(), slug))
        elif len(parts) == 2:
            aliases.append((parts[0].strip(), parts[1].strip()))
        else:
            raise Exception("Error defining column")
    return aliases


# --------------------------------------------------------------------------
# Expression conversion: ast node -> IR Expr
# --------------------------------------------------------------------------
def _convert(node):
    if isinstance(node, ast.Expression):
        return _convert(node.body)

    if isinstance(node, ast.Constant):
        return _convert_constant(node.value)

    if isinstance(node, ast.Name):
        return ir.Name((node.id,))

    if isinstance(node, ast.Attribute):
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        parts.append(cur.id)  # the root ast.Name
        return ir.Name(tuple(reversed(parts)))

    if isinstance(node, ast.BinOp):
        return ir.BinaryOp(_BINOP[type(node.op)], _convert(node.left), _convert(node.right))

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return ir.Unary(ir.Op.SUB, _convert(node.operand))
        if isinstance(node.op, ast.Not):
            return ir.Not(_convert(node.operand))
        if isinstance(node.op, ast.UAdd):
            return _convert(node.operand)
        raise NotImplementedError(f"Unary op: {ast.dump(node)}")

    if isinstance(node, ast.BoolOp):
        kind = ir.BoolKind.AND if isinstance(node.op, ast.And) else ir.BoolKind.OR
        return ir.BoolOp(kind, tuple(_convert(v) for v in node.values))

    if isinstance(node, ast.Compare):
        # a < b  (single)  or  a < b < c  (chained -> AND of pairs)
        comparisons = []
        left = _convert(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = _convert(comparator)
            comparisons.append(ir.BinaryOp(_CMPOP[type(op)], left, right))
            left = right
        if len(comparisons) == 1:
            return comparisons[0]
        return ir.BoolOp(ir.BoolKind.AND, tuple(comparisons))

    if isinstance(node, ast.Call):
        return ir.Func(node.func.id.lower(), tuple(_convert(a) for a in node.args))

    if isinstance(node, ast.Tuple):
        return ir.TupleExpr(tuple(_convert(e) for e in node.elts))

    if isinstance(node, ast.Set):
        # the {name} placeholder syntax parses as a one-element set literal
        elt = node.elts[0]
        return ir.Param(elt.id)

    raise NotImplementedError(f"Unsupported expression: {ast.dump(node)}")


def _convert_constant(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("@"):
            return ir.NamedRef(stripped[1:])
        if stripped.upper().startswith("SELECT "):
            return ir.RawSQL(value)
        return ir.Literal(value)
    return ir.Literal(value)


def convert_expression(src):
    """Parse a single Djaq expression string into an IR expression."""
    return _convert(ast.parse(src, mode="eval"))


# --------------------------------------------------------------------------
# Query assembly
# --------------------------------------------------------------------------
def parse_order_by(order_by_src):
    """Parse an order-by source into a list of :class:`~djaq.query.ir.Order`."""
    s = order_by_src.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    orders = []
    for term in split_columns(s):
        direction = ir.Direction.ASC
        if term.startswith("-"):
            direction = ir.Direction.DESC
            term = term[1:].strip()
        elif term.startswith("+"):
            term = term[1:].strip()
        orders.append(ir.Order(convert_expression(term), direction))
    return orders


def parse(
    model,
    select_src,
    where_src=None,
    order_by_src=None,
    limit=None,
    offset=None,
    distinct=False,
    local=False,
):
    """Build an unresolved :class:`~djaq.query.ir.Query` from source strings."""
    select_src = select_src.replace("\n", " ")
    projections = [
        ir.Projection(convert_expression(expr_str), alias)
        for expr_str, alias in parse_column_aliases(select_src)
    ]
    where = convert_expression(where_src) if where_src else None
    order_by = parse_order_by(order_by_src) if order_by_src else []
    return ir.Query(
        model=model,
        projections=projections,
        where=where,
        order_by=order_by,
        limit=limit,
        offset=offset,
        distinct=distinct,
        local=local,
    )
