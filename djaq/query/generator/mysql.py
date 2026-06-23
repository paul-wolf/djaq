"""MySQL dialect.

PROVISIONAL: written from the SQL spec and unit-tested at the string level, but
not yet verified against a live MySQL server. When a server is available, run
``DJAQ_DB=mysql`` against the conformance suite and treat any failure as the
spec to fix here (the same ratchet used for SQLite).

Differences from the Postgres-centric base: backtick identifier quoting,
``CONCAT(...)`` instead of ``||`` (``||`` is logical OR in MySQL), regex via the
``REGEXP`` operator, case-insensitive LIKE via ``LOWER()``, ``CAST`` target-type
remapping (MySQL casts to ``SIGNED``/``CHAR``/..., not ``int``), date parts via
``EXTRACT``, and ``OFFSET`` requiring a ``LIMIT``.
"""

from .base import Dialect


class MySQLDialect(Dialect):
    name = "mysql"

    # Djaq/neutral cast targets -> MySQL CAST types (MySQL rejects e.g. "int").
    _CAST_TYPES = {
        "int": "SIGNED",
        "integer": "SIGNED",
        "bigint": "SIGNED",
        "smallint": "SIGNED",
        "bool": "SIGNED",
        "boolean": "SIGNED",
        "decimal": "DECIMAL",
        "float": "DECIMAL",
        "string": "CHAR",
        "text": "CHAR",
        "char": "CHAR",
        "date": "DATE",
        "datetime": "DATETIME",
        "time": "TIME",
    }

    _DATE_UNITS = {
        "year": "YEAR",
        "month": "MONTH",
        "day": "DAY",
        "hour": "HOUR",
        "minute": "MINUTE",
        "second": "SECOND",
    }

    def quote_ident(self, ident: str) -> str:
        return f"`{ident}`"

    def quote_table(self, table: str) -> str:
        return f"`{table}`"

    def cast(self, expr_sql: str, type_sql: str) -> str:
        t = type_sql.replace("'", "").strip().lower()
        return f"CAST({expr_sql} AS {self._CAST_TYPES.get(t, t.upper())})"

    def date_extract(self, part: str, expr_sql: str) -> str:
        if part.lower() == "date":
            return f"DATE({expr_sql})"
        unit = self._DATE_UNITS.get(part.lower(), part.upper())
        return f"EXTRACT({unit} FROM {expr_sql})"

    def limit_offset(self, limit, offset) -> str:
        if offset and not limit:
            # MySQL requires a LIMIT before OFFSET; use the documented maximum.
            return f" LIMIT 18446744073709551615 OFFSET {int(offset)}"
        return super().limit_offset(limit, offset)

    @property
    def functions(self):
        fns = super().functions
        fns["concat"] = lambda d, a: f"CONCAT({', '.join(a)})"
        fns["ilike"] = lambda d, a: f"LOWER({a[0]}) LIKE LOWER({a[1]})"
        fns["regex"] = lambda d, a: f"{a[0]} REGEXP {a[1]}"
        return fns
