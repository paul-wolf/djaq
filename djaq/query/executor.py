"""Execution: run a parser's SQL and materialise rows.

The ``Executor`` holds a reference to its owning ``ExpressionParser`` and reads
the built SQL, connection, column headers and context from it. The cursor lives
on the parser so that the parser's ``rewind()``/``context()`` invalidation
(setting ``cursor = None``) continues to work.
"""

import csv
import io
import json

from django.core.serializers.json import DjangoJSONEncoder

from djaq.result import DQResult


class Executor:
    def __init__(self, parser):
        self.p = parser

    def execute(self, context=None, count=False):
        """Create a cursor and execute the built SQL."""
        p = self.p
        p.context(context)
        sql = p.sql
        p.cursor = p.connection.cursor()

        if count:
            sql = f"SELECT COUNT(*) FROM ({sql}) c"

        if p._context or p._extra_named:
            bind = (
                p.context_validator_class(p, p._context).context()
                if p._context
                else {}
            )
            # IN-list parameters were expanded into indexed named placeholders.
            bind.update(p._extra_named)
            if p.verbosity:
                print(f"sql={sql}, params={bind}")
            p.cursor.execute(sql, bind)
        else:
            if p.verbosity:
                print(f"sql={sql}")
            p.cursor.execute(sql)

    def _prepare(self, data):
        """Build the SQL and open a cursor if not already done."""
        if not self.p.sql:
            self.p.construct()
        if not self.p.cursor:
            self.execute(data)

    def dicts(self, data=None):
        p = self.p
        self._prepare(data)
        while True:
            row = p.cursor.fetchone()
            if row is None:
                break
            yield dict(zip(p.column_headers, row))
        p.cursor = None

    def tuples(self, data=None, flat=False):
        p = self.p
        self._prepare(data)
        while True:
            row = p.cursor.fetchone()
            if row is None:
                break
            yield row[0] if flat else row
        p.cursor = None

    def json(self, data=None, encoder=DjangoJSONEncoder):
        for d in self.dicts(data):
            yield json.dumps(d, cls=encoder)
        self.p.cursor = None

    def objs(self, data=None):
        p = self.p
        self._prepare(data)
        while True:
            row = p.cursor.fetchone()
            if row is None:
                break
            yield DQResult(dict(zip(p.column_headers, row)), dq=p)
        p.cursor = None

    def next(self, data=None):
        p = self.p
        self._prepare(data)
        row = p.cursor.fetchone()
        return DQResult(dict(zip(p.column_headers, row)), dq=p)

    def csv(self, data=None):
        p = self.p
        self._prepare(data)
        while True:
            output = io.StringIO()
            row = p.cursor.fetchone()
            if row is None:
                break
            writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
            writer.writerow(row)
            yield output.getvalue()
        p.cursor = None

    def value(self, data=None):
        for t in self.tuples(data=data):
            return t[0]

    def count(self, data=None):
        p = self.p
        if not p.sql:
            p.construct()
        self.execute(data, count=True)
        return p.cursor.fetchone()[0]
