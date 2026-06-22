"""Djaq query engine.

This package was historically a single ~1500-line module. It is being
decomposed along its natural responsibilities:

    context.py       - context data handling (ContextValidator, has_context)
    conditions.py    - rendering B() condition trees to strings
    sql_functions.py - the SQL function catalogue (djaq_functions, aggregates)
    relations.py     - the join-graph node (JoinRelation)
    parser.py        - ExpressionParser (parse + resolve + generate, for now)
    api.py           - DjaqQuery, the fluent public API

The names below are re-exported to preserve the public import surface
(``from djaq.query import DjaqQuery``, ``djaq_functions``, ``render_conditions``).
"""

from .sql_functions import (
    djaq_functions,
    aggregate_functions,
    concat,
    cast,
    index_choice0,
    func_in_whitelist,
    build_case_statement_from_choices,
)
from .context import ContextValidator, has_context, PLACEHOLDER_PATTERN
from .conditions import render_conditions, render_conditions_drop_empty
from .relations import JoinRelation
from .parser import ExpressionParser
from .api import DjaqQuery

__all__ = [
    "DjaqQuery",
    "ExpressionParser",
    "JoinRelation",
    "ContextValidator",
    "djaq_functions",
    "aggregate_functions",
    "render_conditions",
    "render_conditions_drop_empty",
    "has_context",
    "PLACEHOLDER_PATTERN",
    "build_case_statement_from_choices",
    "concat",
    "cast",
    "index_choice0",
    "func_in_whitelist",
]
