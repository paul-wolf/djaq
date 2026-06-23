"""Djaq intermediate representation (IR).

This module is the boundary between parsing and SQL generation. It is pure
data: it imports no Django models and emits no SQL. The frontend produces an
unresolved ``Query`` (expressions contain ``Name`` nodes); the resolver rewrites
it into a ``ResolvedQuery`` (``Name`` -> ``FieldRef``/``DateExtract``/``Case``,
functions classified, join graph and GROUP BY filled in); the generator walks
the resolved tree to produce ``(sql, params)``.

See the ``djaq-ir-design`` design note for the full rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------
class Op(Enum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    EQ = "="
    NE = "<>"
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="
    IS = "IS"
    IS_NOT = "IS NOT"
    IN = "IN"
    NOT_IN = "NOT IN"


class BoolKind(Enum):
    AND = "AND"
    OR = "OR"


class FuncKind(Enum):
    """Whether a function aggregates (and therefore forces a GROUP BY).

    Rendering is decided separately by the dialect: a name present in the
    dialect's function table is rendered from a template (e.g. ``sumif``,
    ``iif``, ``concat``), otherwise it is rendered generically as
    ``NAME(args)``. So an aggregate can still be template-rendered.
    """

    AGGREGATE = "aggregate"
    SCALAR = "scalar"


class Direction(Enum):
    ASC = "ASC"
    DESC = "DESC"


# --------------------------------------------------------------------------
# Function catalogues (dialect-neutral classification)
# --------------------------------------------------------------------------
#: Functions that aggregate rows -> presence forces grouping by the non-aggregate
#: projections. This is a single shared set (not per-vendor), which is what fixes
#: the historical bug where ``sumif`` grouped on Postgres but not SQLite.
AGGREGATE_FUNCS = frozenset(
    {
        "avg",
        "count",
        "countdistinct",
        "max",
        "min",
        "sum",
        "sumif",
        "stddev",
        "variance",
        "group_concat",
        "total",
    }
)

#: Functions with bespoke per-dialect rendering that are NOT aggregates.
#: (Aggregate templates such as ``sumif``/``countdistinct`` live in
#: ``AGGREGATE_FUNCS`` above but are also dialect-rendered.)
TEMPLATE_FUNCS = frozenset(
    {
        "iif",
        "like",
        "ilike",
        "regex",
        "concat",
        "cast",
        "today",
        "pointx",
        "pointy",
        "index_choice0",
    }
)


# --------------------------------------------------------------------------
# Leaf expressions (frontend output)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Literal:
    value: object  # str | int | float | bool | None


@dataclass(frozen=True)
class Param:
    """A named context parameter, written ``{name}`` in source."""

    name: str


@dataclass(frozen=True)
class Name:
    """An unresolved dotted reference, e.g. ``publisher.owner.name``.

    Produced by the frontend; replaced by the resolver.
    """

    path: tuple[str, ...]


# --------------------------------------------------------------------------
# Resolved leaves (resolver output)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldRef:
    """A concrete column on a relation in the join graph."""

    relation: "Relation"
    column: str
    field: object = None  # the Django field, for type information


@dataclass(frozen=True)
class DateExtract:
    """A date/datetime part access, e.g. ``pubdate.year``."""

    part: str  # year | month | day | ...
    source: "Expr"


@dataclass(frozen=True)
class Case:
    """A CASE expression, e.g. the rewrite of a ``*_display`` choice field."""

    whens: tuple[tuple["Expr", "Expr"], ...]  # (condition, result) pairs
    default: Optional["Expr"] = None


# --------------------------------------------------------------------------
# Composite expressions
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class BinaryOp:
    op: Op
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class BoolOp:
    kind: BoolKind
    operands: tuple["Expr", ...]


@dataclass(frozen=True)
class Not:
    operand: "Expr"


@dataclass(frozen=True)
class Unary:
    op: Op  # SUB for negation
    operand: "Expr"


@dataclass(frozen=True)
class Func:
    name: str  # lower-cased
    args: tuple["Expr", ...] = ()
    kind: Optional[FuncKind] = None  # filled by the resolver


@dataclass(frozen=True)
class TupleExpr:
    """A parenthesised list: projection groups and IN value-lists."""

    elements: tuple["Expr", ...]


@dataclass(frozen=True)
class NamedRef:
    """A reference to a named object, written ``@name`` in source.

    Resolved later (against the query directory) into a ``Subquery`` or
    ``RawSQL`` depending on whether the target is a DjaqQuery, QuerySet or list.
    """

    name: str


@dataclass(frozen=True)
class Subquery:
    query: "ResolvedQuery"


@dataclass(frozen=True)
class RawSQL:
    """Literal SQL passthrough; only emitted when the query is ``local``."""

    sql: str
    params: tuple = ()


Expr = Union[
    Literal,
    Param,
    Name,
    FieldRef,
    DateExtract,
    Case,
    BinaryOp,
    BoolOp,
    Not,
    Unary,
    Func,
    TupleExpr,
    NamedRef,
    Subquery,
    RawSQL,
]


# --------------------------------------------------------------------------
# Join graph
# --------------------------------------------------------------------------
@dataclass
class Relation:
    """A node in the join graph. Pure structure -- no SQL strings, no ORM.

    ``relations[0]`` of a query is the root (the FROM table). Every other
    relation references its ``parent`` relation and carries ``join_pairs`` --
    ``(parent_column, this_column)`` tuples that express its ON condition
    relative to the parent. Joining by *relation reference* (rather than table
    name) is what makes aliasing honest: two relations on the same table, or a
    self-join, stay distinct because each carries its own ``alias`` and the ON
    clause uses ``parent.ref``/``self.ref``. ``path`` (the relation-name path
    from the root) is the de-duplication key. ``entity`` is the schema entity
    used by the resolver for field lookup (``None`` for an m2m link table).
    """

    table: str
    entity: object = None
    alias: Optional[str] = None
    parent: Optional["Relation"] = None
    join_pairs: tuple = ()  # ((parent_column, this_column), ...)
    join_type: str = "->"  # -> left, <- right, <> inner
    path: tuple = ()

    @property
    def ref(self) -> str:
        """How this relation is referenced in SQL (alias if any, else table)."""
        return self.alias or self.table


# --------------------------------------------------------------------------
# Query structure
# --------------------------------------------------------------------------
@dataclass
class Projection:
    expr: Expr
    alias: str


@dataclass
class Order:
    expr: Expr
    direction: Direction = Direction.ASC


@dataclass
class Query:
    """Unresolved query (frontend output)."""

    model: object
    projections: list[Projection] = field(default_factory=list)
    where: Optional[Expr] = None
    order_by: list[Order] = field(default_factory=list)
    limit: Optional[int] = None
    offset: Optional[int] = None
    distinct: bool = False
    local: bool = False


@dataclass
class ResolvedQuery(Query):
    """Resolved query (resolver output): adds the join graph and grouping."""

    relations: list[Relation] = field(default_factory=list)
    group_by: list[Expr] = field(default_factory=list)


# --------------------------------------------------------------------------
# Traversal helpers
# --------------------------------------------------------------------------
def children(node: Expr) -> tuple[Expr, ...]:
    """Return the direct child expressions of ``node`` (for traversal)."""
    if isinstance(node, (Literal, Param, Name, FieldRef, RawSQL, NamedRef)):
        return ()
    if isinstance(node, DateExtract):
        return (node.source,)
    if isinstance(node, Case):
        out: list[Expr] = []
        for cond, result in node.whens:
            out.extend((cond, result))
        if node.default is not None:
            out.append(node.default)
        return tuple(out)
    if isinstance(node, BinaryOp):
        return (node.left, node.right)
    if isinstance(node, BoolOp):
        return tuple(node.operands)
    if isinstance(node, Not):
        return (node.operand,)
    if isinstance(node, Unary):
        return (node.operand,)
    if isinstance(node, Func):
        return tuple(node.args)
    if isinstance(node, TupleExpr):
        return tuple(node.elements)
    if isinstance(node, Subquery):
        return ()  # the subquery is a separate query, not an expression child
    raise TypeError(f"Unknown IR node: {type(node).__name__}")


def walk(node: Expr):
    """Yield ``node`` and all descendant expressions, depth-first."""
    yield node
    for child in children(node):
        yield from walk(child)


def contains_aggregate(node: Expr) -> bool:
    """True if ``node`` or any descendant is an aggregate function call."""
    return any(
        isinstance(n, Func) and n.kind is FuncKind.AGGREGATE for n in walk(node)
    )
