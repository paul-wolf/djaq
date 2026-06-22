"""SQL generator package: ``SQLGenerator`` plus per-vendor dialects."""

from .base import Dialect, SQLGenerator
from .postgres import PostgresDialect

#: Django ``connection.vendor`` -> Dialect class.
_DIALECTS = {
    "postgresql": PostgresDialect,
}


def get_dialect(vendor: str) -> Dialect:
    """Return a Dialect instance for a Django connection vendor."""
    return _DIALECTS.get(vendor, Dialect)()


__all__ = ["Dialect", "SQLGenerator", "PostgresDialect", "get_dialect"]
