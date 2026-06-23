"""SQL generator package: ``SQLGenerator`` plus per-vendor dialects."""

from .base import Dialect, SQLGenerator
from .postgres import PostgresDialect
from .sqlite import SQLiteDialect
from .mysql import MySQLDialect

#: Django ``connection.vendor`` -> Dialect class.
_DIALECTS = {
    "postgresql": PostgresDialect,
    "sqlite": SQLiteDialect,
    "mysql": MySQLDialect,
}


def get_dialect(vendor: str) -> Dialect:
    """Return a Dialect instance for a Django connection vendor."""
    return _DIALECTS.get(vendor, Dialect)()


__all__ = [
    "Dialect",
    "SQLGenerator",
    "PostgresDialect",
    "SQLiteDialect",
    "MySQLDialect",
    "get_dialect",
]
