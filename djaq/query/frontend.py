"""Frontend: Djaq source text -> unresolved :class:`~djaq.query.ir.Query`.

Structural only: it produces IR nodes and performs no model lookups and no SQL
generation. Expressions are parsed by a hand-written lexer + recursive-descent
parser (``_tokenize`` / ``_Parser``) -- no Python ``ast`` -- so the Djaq grammar
is owned here, and the resolver and generator are untouched.
"""

import re
import unicodedata

from . import ir


def _slugify(value):
    """Vendored equivalent of django.utils.text.slugify(allow_unicode=False).

    Kept local so the frontend (and the whole parse->resolve->generate path)
    has no Django dependency. Used only to derive default column aliases.
    """
    value = (
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


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
            slug = _slugify(parts[0].replace(".", "_").replace(" ", "_")).replace(
                "-", "_"
            )
            aliases.append((parts[0].strip(), slug))
        elif len(parts) == 2:
            aliases.append((parts[0].strip(), parts[1].strip()))
        else:
            raise Exception("Error defining column")
    return aliases


# --------------------------------------------------------------------------
# Expression lexer
# --------------------------------------------------------------------------
_TWO_CHAR_OPS = {"==", "!=", ">=", "<="}
_COMPARE_OPS = {
    "==": ir.Op.EQ,
    "!=": ir.Op.NE,
    ">": ir.Op.GT,
    "<": ir.Op.LT,
    ">=": ir.Op.GE,
    "<=": ir.Op.LE,
}


def _tokenize(src):
    """Lex a Djaq expression into a list of ``(kind, value)`` tokens."""
    tokens = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif c == "{":  # {name} parameter placeholder
            j = src.find("}", i)
            if j == -1:
                raise SyntaxError(f"unterminated parameter in {src!r}")
            tokens.append(("param", src[i + 1 : j].strip()))
            i = j + 1
        elif c in "'\"":  # string literal
            quote, j, buf = c, i + 1, []
            while j < n and src[j] != quote:
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j + 1])
                    j += 2
                else:
                    buf.append(src[j])
                    j += 1
            tokens.append(("str", "".join(buf)))
            i = j + 1
        elif c.isdigit():  # int or float
            j = i
            while j < n and src[j].isdigit():
                j += 1
            if j < n and src[j] == "." and j + 1 < n and src[j + 1].isdigit():
                j += 1
                while j < n and src[j].isdigit():
                    j += 1
                tokens.append(("num", float(src[i:j])))
            else:
                tokens.append(("num", int(src[i:j])))
            i = j
        elif c.isalpha() or c == "_":  # name or keyword
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            tokens.append(("name", src[i:j]))
            i = j
        elif src[i : i + 2] in _TWO_CHAR_OPS:
            tokens.append(("op", src[i : i + 2]))
            i += 2
        elif c in "><+-*/":
            tokens.append(("op", c))
            i += 1
        elif c == "(":
            tokens.append(("lparen", c))
            i += 1
        elif c == ")":
            tokens.append(("rparen", c))
            i += 1
        elif c == ",":
            tokens.append(("comma", c))
            i += 1
        elif c == ".":
            tokens.append(("dot", c))
            i += 1
        else:
            raise SyntaxError(f"unexpected character {c!r} in {src!r}")
    return tokens


# --------------------------------------------------------------------------
# Recursive-descent parser: tokens -> IR Expr
# --------------------------------------------------------------------------
class _Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else (None, None)

    def _advance(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def _keyword(self, *words):
        kind, value = self._peek()
        return kind == "name" and value in words

    def _expect(self, kind):
        if self._peek()[0] != kind:
            raise SyntaxError(f"expected {kind}, got {self._peek()}")
        return self._advance()

    def parse(self):
        expr = self._or()
        if self.pos != len(self.toks):
            raise SyntaxError(f"unexpected trailing tokens: {self.toks[self.pos:]}")
        return expr

    def _or(self):
        operands = [self._and()]
        while self._keyword("or"):
            self._advance()
            operands.append(self._and())
        return operands[0] if len(operands) == 1 else ir.BoolOp(ir.BoolKind.OR, tuple(operands))

    def _and(self):
        operands = [self._not()]
        while self._keyword("and"):
            self._advance()
            operands.append(self._not())
        return operands[0] if len(operands) == 1 else ir.BoolOp(ir.BoolKind.AND, tuple(operands))

    def _not(self):
        if self._keyword("not"):
            self._advance()
            return ir.Not(self._not())
        return self._comparison()

    def _comparison(self):
        left = self._additive()
        comps = []
        while True:
            op = self._comparison_op()
            if op is None:
                break
            right = self._additive()
            comps.append(ir.BinaryOp(op, left, right))
            left = right
        if not comps:
            return left
        return comps[0] if len(comps) == 1 else ir.BoolOp(ir.BoolKind.AND, tuple(comps))

    def _comparison_op(self):
        kind, value = self._peek()
        if kind == "op" and value in _COMPARE_OPS:
            self._advance()
            return _COMPARE_OPS[value]
        if self._keyword("is"):
            self._advance()
            if self._keyword("not"):
                self._advance()
                return ir.Op.IS_NOT
            return ir.Op.IS
        if self._keyword("in"):
            self._advance()
            return ir.Op.IN
        if self._keyword("not"):  # only the infix 'not in'
            nxt = self.toks[self.pos + 1] if self.pos + 1 < len(self.toks) else None
            if nxt == ("name", "in"):
                self._advance()
                self._advance()
                return ir.Op.NOT_IN
        return None

    def _additive(self):
        left = self._multiplicative()
        while self._peek()[0] == "op" and self._peek()[1] in ("+", "-"):
            op = ir.Op.ADD if self._advance()[1] == "+" else ir.Op.SUB
            left = ir.BinaryOp(op, left, self._multiplicative())
        return left

    def _multiplicative(self):
        left = self._unary()
        while self._peek()[0] == "op" and self._peek()[1] in ("*", "/"):
            op = ir.Op.MUL if self._advance()[1] == "*" else ir.Op.DIV
            left = ir.BinaryOp(op, left, self._unary())
        return left

    def _unary(self):
        if self._peek() == ("op", "-"):
            self._advance()
            return ir.Unary(ir.Op.SUB, self._unary())
        if self._peek() == ("op", "+"):
            self._advance()
            return self._unary()
        return self._primary()

    def _primary(self):
        kind, value = self._peek()
        if kind == "num":
            self._advance()
            return ir.Literal(value)
        if kind == "param":
            self._advance()
            return ir.Param(value)
        if kind == "str":
            self._advance()
            return _string_literal(value)
        if kind == "lparen":
            return self._parenthesised()
        if kind == "name":
            self._advance()
            if value in ("True", "False", "None"):
                return ir.Literal({"True": True, "False": False, "None": None}[value])
            if self._peek()[0] == "lparen":  # function call
                return ir.Func(value.lower(), tuple(self._call_args()))
            path = [value]  # dotted attribute reference
            while self._peek()[0] == "dot":
                self._advance()
                path.append(self._expect("name")[1])
            return ir.Name(tuple(path))
        raise SyntaxError(f"unexpected token {self._peek()}")

    def _parenthesised(self):
        self._expect("lparen")
        elements = [self._or()]
        while self._peek()[0] == "comma":
            self._advance()
            elements.append(self._or())
        self._expect("rparen")
        return elements[0] if len(elements) == 1 else ir.TupleExpr(tuple(elements))

    def _call_args(self):
        self._expect("lparen")
        args = []
        if self._peek()[0] != "rparen":
            args.append(self._or())
            while self._peek()[0] == "comma":
                self._advance()
                args.append(self._or())
        self._expect("rparen")
        return args


def _string_literal(value):
    stripped = value.strip()
    if stripped.startswith("@"):
        return ir.NamedRef(stripped[1:])
    if stripped.upper().startswith("SELECT "):
        return ir.RawSQL(value)
    return ir.Literal(value)


def convert_expression(src):
    """Parse a single Djaq expression string into an IR expression."""
    return _Parser(_tokenize(src)).parse()


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
