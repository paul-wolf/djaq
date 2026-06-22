"""PostgreSQL dialect.

The base :class:`~djaq.query.generator.base.Dialect` already encodes the
historical (Postgres-centric) behaviour, so this dialect is currently a thin
marker. SQLite and MySQL dialects override the non-portable pieces.
"""

from .base import Dialect


class PostgresDialect(Dialect):
    name = "postgresql"
