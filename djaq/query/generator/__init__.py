"""SQL generator package: ``SQLGenerator`` plus per-vendor dialects."""

from .base import Dialect, SQLGenerator
from .postgres import PostgresDialect
from .sqlite import SQLiteDialect

#: Django ``connection.vendor`` -> Dialect class.
_DIALECTS = {
    "postgresql": PostgresDialect,
    "sqlite": SQLiteDialect,
}


def get_dialect(vendor: str) -> Dialect:
    """Return a Dialect instance for a Django connection vendor."""
    return _DIALECTS.get(vendor, Dialect)()


__all__ = [
    "Dialect",
    "SQLGenerator",
    "PostgresDialect",
    "SQLiteDialect",
    "get_dialect",
]
