import dataclasses
from typing import Dict, Union, List

from django.db import models
from django.core.serializers.json import DjangoJSONEncoder

from djaq.conditions import B
from ..app_utils import (
    find_model_class,
    get_model_details,
    get_schema,
    make_dataclass,
    dataclass_mapper,
)
from .parser import ExpressionParser


class DjaqQuery:
    def __init__(
        self,
        model_source: Union[models.Model, str],
        select_source: Union[str, List, None] = None,
        name: str = None,
        names: Union[Dict, None] = None,
        whitelist=None,
        provider=None,
    ):
        if isinstance(model_source, models.base.ModelBase):
            model = model_source
        elif isinstance(model_source, str):
            model = find_model_class(model_source, whitelist=whitelist)
        else:
            raise Exception(
                f"Type not supported for model source: {type(model_source)}"
            )
        self.name = name
        self.parser = ExpressionParser(
            model=model, whitelist=whitelist, name=name, provider=provider
        )

        if not select_source or select_source == "*":
            if provider is not None:
                # default fields come from the scoped entity, not all of Django's
                fields = provider.get_entity(model._meta.label).fields.keys()
            else:
                fields = get_model_details(model, self.parser.connection)["fields"]
            select_source = ", ".join(fields)
        elif select_source == "pk":
            select_source = model._meta.pk.name

        self.model = model

        # self.condition_node = None
        if isinstance(select_source, str):
            select_source = select_source.strip()
            if not select_source.startswith("("):
                select_source = f"({select_source})"
        elif isinstance(select_source, list):
            select_source = f"({', '.join(select_source)})"
        else:
            raise Exception("Expected str or list for select source")
        self.parser.select_src = select_source

    def update_name_directory(self, cloned_parser):
        """Update the class variable that tracks names of objects for use in subqueries, etc."""
        if self.name in ExpressionParser.directory:
            ExpressionParser.directory[self.name] = cloned_parser
    
    def clone(self):
        c = DjaqQuery(self.model, name=self.name)
        c.parser = self.parser.clone()
        # make sure the new parser has the latest copy of ourselves
        self.update_name_directory(cloned_parser=c.parser)

        return c

    def construct(self):
        self.parser.construct()

    def order_by(self, source: Union[str, List]):
        c = self.clone()
        c.parser.order_by(source)
        return c

    def where(self, node: Union[str, B]):
        c = self.clone()
        c.parser.where(node)
        return c

    # Reads only: mutation lives on djaq.Writer (command-query separation).

    def distinct(self):
        c = self.clone()
        c.parser.distinct = True
        return c

    def dicts(self, data=None):
        # self.construct()
        return self.parser.dicts(data=data)

    def tuples(self, data=None, flat=False):
        # self.construct()
        return self.parser.tuples(data=data, flat=flat)

    def count(self, data=None):
        # self.construct()
        return self.parser.count(data)

    def sql(self):
        self.construct()
        return self.parser.sql

    def rewind(self):
        c = self.clone()
        c.parser.rewind()
        return c

    def csv(self, data=None):
        # self.construct()
        return self.parser.csv(data)

    def limit(self, limit):
        c = self.clone()
        c.parser._limit = limit
        return c

    def offset(self, offset):
        c = self.clone()
        c.parser._offset = offset
        return c

    def context(self, context: Dict, drop_empty=False):
        """Update our context with dict context."""
        c = self.clone()
        
        if not c.parser._context:
            c.parser._context = dict()
        if context:
            c.parser.cursor = None  # cause the query to be re-evaluated
            c.parser._context.update(context)
        c.parser.drop_empty = drop_empty
        return c

    def json(self, data=None, encoder=DjangoJSONEncoder):
        # self.construct()
        return self.parser.json(data, encoder)

    def objs(self, data=None):
        # self.construct()
        return self.parser.objs(data)

    def value(self, data=None):
        # self.construct()
        return self.parser.value(data)

    def dataframe(self, context=None):
        """Return a pandas dataframe.
        This only works if pandas is installed.
        """
        import pandas as pd

        self.construct()
        self.context(context)
        constructed_sql = self.parser.sql
        
        sql = self.parser.mogrify(constructed_sql, self.parser._context)
        df = pd.read_sql(sql, self.parser.connection)
        df.columns = self.parser.column_headers
        return df

    def qs(self):
        self.construct()
        return self.parser.model.objects.raw(self.sql(), self.parser._context)

    def go(self):
        return list(self.rewind().dicts())

    def map(self, result_type: Union[callable, dataclasses.dataclass], data=None):
        """Either map to dataclass or call function to produce result.
        if result_type is a function, the function will receive a dict as a single parameter.
        """
        self.construct()
        if not self.parser.cursor:
            self.parser.execute(data)
        while True:
            row = self.parser.cursor.fetchone()
            if row is None:
                break
            row_dict = dict(zip(self.parser.column_headers, row))
            if dataclasses.is_dataclass(result_type):
                yield dataclass_mapper(result_type, row_dict)
            elif callable(result_type):
                yield result_type(row_dict)

    @property
    def schema(self):
        return get_model_details(self.model, self.parser.connection)

    @classmethod
    def schema_all(cls, connection=None):
        return get_schema(connection)

    def dataclass(self, defaults=False, base_class=None):
        make_dataclass(self.model, defaults, base_class)

    def __len__(self):
        return self.count()

    def __iter__(self):
        return self.dicts()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            pass
        else:
            pass

    def __repr__(self):
        return str(self.limit(5).go()) + "..."
