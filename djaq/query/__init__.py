"""Djaq query engine.

This package was historically a single ~1500-line module. It is now decomposed
along its natural responsibilities, with a dialect-neutral IR between parsing
and SQL generation:

    ir.py            - the intermediate representation (nodes + helpers)
    frontend.py      - Djaq source -> unresolved Query IR
    resolver.py      - bind the IR to model metadata -> ResolvedQuery
    generator/       - ResolvedQuery -> (sql, params), per-dialect
    context.py       - context data handling (ContextValidator, has_context)
    conditions.py    - rendering B() condition trees to strings
    sql_functions.py - the public SQL function catalogue (djaq_functions)
    parser.py        - ExpressionParser, orchestrates the pipeline + execution
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
from .parser import ExpressionParser
from .api import DjaqQuery

__all__ = [
    "DjaqQuery",
    "ExpressionParser",
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
