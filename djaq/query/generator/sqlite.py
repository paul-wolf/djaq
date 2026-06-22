"""SQLite dialect.

Overrides the Postgres-centric defaults where SQLite differs: ``ILIKE`` ->
case-insensitive ``LIKE``, regex via SQLite's ``REGEXP`` operator (Django
registers the function), date parts via ``strftime``, ``CAST(x AS t)`` instead
of ``x::t``, and ``OFFSET`` requiring a ``LIMIT``.
"""

from .base import Dialect


class SQLiteDialect(Dialect):
    name = "sqlite"

    _DATE_PARTS = {
        "year": "%Y",
        "month": "%m",
        "day": "%d",
        "hour": "%H",
        "minute": "%M",
        "second": "%S",
    }

    def date_extract(self, part: str, expr_sql: str) -> str:
        if part.lower() == "date":
            return f"DATE({expr_sql})"
        fmt = self._DATE_PARTS.get(part.lower(), "%Y")
        return f"CAST(strftime('{fmt}', {expr_sql}) AS INTEGER)"

    def cast(self, expr_sql: str, type_sql: str) -> str:
        t = type_sql.replace("'", "")
        return f"CAST({expr_sql} AS {t})"

    def limit_offset(self, limit, offset) -> str:
        # SQLite requires a LIMIT before OFFSET; -1 means "no limit".
        if offset and not limit:
            return f" LIMIT -1 OFFSET {int(offset)}"
        return super().limit_offset(limit, offset)

    @property
    def functions(self):
        fns = super().functions
        fns["ilike"] = lambda d, a: f"{a[0]} LIKE {a[1]}"
        fns["regex"] = lambda d, a: f"{a[0]} REGEXP {a[1]}"
        return fns
