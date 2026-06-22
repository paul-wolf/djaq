import copy
import csv
import io
import json
from typing import Dict, Optional, Union, List

from django.db import connections, models
from django.db.models.query import QuerySet
from django.core.serializers.json import DjangoJSONEncoder

from djaq.result import DQResult
from djaq.conditions import B
from .context import ContextValidator
from .conditions import render_conditions, render_conditions_drop_empty
from . import frontend
from .resolver import Resolver
from .generator import SQLGenerator, get_dialect


class ExpressionParser:
    """Orchestrates the IR pipeline and owns query execution.

    Source strings in, results out: ``construct()`` runs frontend -> resolver ->
    generator to build ``self.sql``; the ``dicts``/``tuples``/``json``/... methods
    execute it. Named instances are tracked in ``directory`` for ``@name``
    subquery references.
    """

    # keep a record of named instances
    directory = {}

    def __init__(
        self,
        model: models.Model = None,  # django model  or string of model
        select_src: str = None,
        where_src: str = None,
        order_by_src: str = None,
        using: str = "default",
        limit: int = None,
        offset: int = None,
        # name given to this object for lookup later
        name: str = None,
        context: Dict = None,
        names: List[str] = None,
        verbosity=0,
        whitelist=None,
        local: bool = False,
        drop_empty: bool = False,
    ):
        # main relation, type is models.Model
        self.model = model

        self._context = context

        if name:
            self.__class__.directory[name] = self

        # these can be names of other objects
        if names:
            self.__class__.directory.update(names)

        self.select_src = select_src
        self.where_src = where_src
        self.order_by_src = order_by_src
        self.using = using
        self.connection = connections[using]
        self.vendor = self.connection.vendor
        self.whitelist = whitelist
        self.verbosity = verbosity
        self._limit = limit
        self._offset = offset
        self.sql = None
        self.cursor = None
        self.parameters = list()  # populated by the generator in construct()
        self.context_validator_class = ContextValidator
        self.local = local
        self.distinct = False
        self.drop_empty = drop_empty

        # a set of conditions defined by B nodes
        self.condition_node: Optional[B] = None
        self.column_headers = list()

    def clone(self):
        p = ExpressionParser(
            self.model,
            select_src=self.select_src,
            where_src=self.where_src,
            order_by_src=self.order_by_src,
            using=self.using,
            limit=self._limit,
            offset=self._offset,
            context=copy.deepcopy(self._context),
            verbosity=self.verbosity,
            whitelist=self.whitelist,
            local=self.local,
            drop_empty=self.drop_empty,
        )
        p.condition_node = copy.deepcopy(self.condition_node)
        p.sql = None
        p.cursor = None
        return p

    def mogrify(self, sql, parameters):
        """Create completed sql with list of parameters.

        TODO: Only works for Postgresql.

        """

        conn = connections[self.using]
        cursor = conn.cursor()
        mogrified = cursor.mogrify(sql, parameters)
        if isinstance(mogrified, bytes):
            return mogrified.decode()
        return mogrified

    def dump(self):
        for k, v in self.__dict__.items():
            print(f"{k}={v}")

    def conditions(self, node: B):
        self.condition_node = node
        return self

    def resolve_name(self, name):
        if name in self.__class__.directory:
            return self.__class__.directory[name]
        # check locals, globals
        else:
            # TODO: throw exception
            return None

    def queryset_source(self, queryset):
        sql, sql_params = queryset.query.get_compiler(
            connection=self.connection
        ).as_sql()
        return sql, sql_params

    def rewind(self):
        """Rewind cursor by setting to None.
        The next time a generator method is called,
        the query will be executed again.
        """
        # self.relations = list()
        self.cursor = None
        return self

    def limit(self, limit):
        self._limit = limit
        return self

    def offset(self, offset):
        self._offset = offset
        return self

    def context(self, context):
        """Update our context with dict context."""
        if not self._context:
            self._context = {}
        if context:
            self.cursor = None  # cause the query to be re-evaluated
            self._context.update(context)
        return self

    def validator(self, validator_class):
        """Set validator_class that
        will check and mutate context variables."""
        if validator_class:
            self.context_validator_class = validator_class
        return self

    def execute(self, context=None, count=False):
        """Create a cursor and execute the sql."""

        self.context(context)

        sql = self.sql
        

        self.cursor = self.connection.cursor()

        if count:
            sql = f"SELECT COUNT(*) FROM ({sql}) c"

        
        if len(self._context):
            context = self.context_validator_class(self, self._context).context()
            if self.verbosity:
                print(f"sql={sql}, params={context}")

            self.cursor.execute(sql, context)
        else:
            if self.verbosity:
                print(f"sql={sql}")

            self.cursor.execute(sql)

    def query(self, context=None):
        """Return source for djaqquery and parameters."""
        self.context(context)
        
        self.construct()
        sql = self.sql
        return sql, self.parameters

    def where(self, node: Union[str, B]):
        if not node:
            return
        
        if isinstance(node, str):
            node = B(node)
        elif isinstance(node, B):
            # no need to do anything
            pass
        if self.condition_node:
            self.condition_node &= node
        else:
            self.condition_node = node
        return self

    def order_by(self, source: Union[str, List]):
        if not source:
            return
        if isinstance(source, str):
            self.order_by_src = source.strip()
        elif isinstance(source, list):
            self.order_by_src = f"({', '.join(source)})"
        else:
            raise Exception("Expected str or list for order by source")

    def _resolve_named(self, name):
        """Resolve an ``@name`` reference to ``(sql, params)`` for a subquery.

        Ported from the old ``visit_Str`` handling: a named DjaqQuery inherits
        its context into ours; a QuerySet is compiled and mogrified to literal
        SQL; a list becomes a literal value tuple (local queries only).
        """
        obj = self.resolve_name(name)
        if isinstance(obj, ExpressionParser):
            self.context(obj._context)
            return obj.query()
        if isinstance(obj, list):
            if not self.local:
                raise Exception("Non-local attempt to use literal SQL")
            return str(tuple(obj)).strip("(").strip(")"), ()
        if isinstance(obj, QuerySet):
            sql, sql_params = self.queryset_source(obj)
            return self.mogrify(sql, sql_params), ()
        raise Exception(f"Name not found: {name}")

    def construct(self):
        """Build the final SQL into ``self.sql`` via the IR pipeline.

        frontend (source -> IR) -> resolver (bind to schema) -> generator
        (IR -> SQL for the connection's dialect).
        """
        src = self.where_src
        if self.condition_node:
            if self.where_src:
                src += " and "
            else:
                src = ""
            if self.drop_empty:
                src += render_conditions_drop_empty(self.condition_node, self._context)
            else:
                src += render_conditions(self.condition_node, self._context)

        query = frontend.parse(
            self.model,
            self.select_src,
            where_src=src or None,
            order_by_src=self.order_by_src,
            limit=self._limit,
            offset=self._offset,
            distinct=self.distinct,
            local=self.local,
        )
        self.column_headers = [p.alias for p in query.projections]
        resolved = Resolver(self.model, whitelist=self.whitelist).resolve(query)
        generator = SQLGenerator(
            get_dialect(self.vendor), named_resolver=self._resolve_named
        )
        self.sql, self.parameters = generator.generate(resolved)

    def dicts(self, data=None):
        if not self.sql:
            self.construct()
        if not self.cursor:
            self.execute(data)
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            row_dict = dict(zip(self.column_headers, row))
            yield row_dict
        self.cursor = None

    def tuples(self, data=None, flat=False):
        if not self.sql:
            self.construct()
        row = None
        if not self.cursor:
            self.execute(data)
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            if flat:
                yield row[0]
            else:
                yield row
        self.cursor = None

    def json(self, data=None, encoder=DjangoJSONEncoder):
        for d in self.dicts(data):
            yield json.dumps(d, cls=encoder)
        self.cursor = None

    def objs(self, data=None):
        if not self.sql:
            self.construct()
        if not self.cursor:
            self.execute(data)
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            row_dict = dict(zip(self.column_headers, row))
            yield DQResult(row_dict, dq=self)
        self.cursor = None

    def next(self, data=None):
        if not self.sql:
            self.construct()
        if not self.cursor:
            self.execute(data)
        row = self.cursor.fetchone()
        row_dict = dict(zip(self.column_headers, row))
        return DQResult(row_dict, dq=self)

    def csv(self, data=None):
        if not self.sql:
            self.construct()
        if not self.cursor:
            self.execute(data)
        while True:
            output = io.StringIO()
            row = self.cursor.fetchone()
            if row is None:
                break
            writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
            writer.writerow(row)
            yield output.getvalue()
        self.cursor = None

    def value(self, data=None):
        for t in self.tuples(data=data):
            return t[0]

    def count(self, data=None):
        if not self.sql:
            self.construct()
        self.execute(data, count=True)
        return self.cursor.fetchone()[0]

    def __repr__(self):
        return f"{self.__class__.__name__}"

    def __str__(self):
        my_list = []
        for i, d in enumerate(self.dicts()):
            my_list.append(d)
            if i == 10:
                break
        return str(my_list)

    def __iter__(self):
        return self.objs()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            pass
        else:
            pass
