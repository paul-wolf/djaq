import copy
from typing import TYPE_CHECKING

from django.db import models
from django.db.models.fields.related import ManyToOneRel, ManyToManyField

from ..app_utils import model_path

if TYPE_CHECKING:
    from .parser import ExpressionParser


class JoinRelation(object):
    JOIN_TYPES = {"->": "LEFT JOIN", "<-": "RIGHT JOIN", "<>": "INNER JOIN"}

    def __init__(
        self,
        model: models.Model,
        xquery: "ExpressionParser",
        fk_relation: "JoinRelation" = None,
        fk_field=None,
        related_field=None,
        join_type: str = "->",
        alias: str = None,
    ):

        self.model = model
        self.fk_relation = fk_relation
        self.fk_field = fk_field
        self.related_field = related_field
        self.join_type = join_type  # left, right, inner
        self.alias = alias
        self.select = ""
        self.expression_str = ""
        self.column_expressions = []
        self.where = ""
        self.group_by = False
        self.order_by = ""
        self.order_by_direction = "+"
        self.xquery = xquery
        self.src = None

    def dump(self):
        r = self
        print(f"   join         : {r.join_type}")
        print(f"   fk_relation  : {r.fk_relation}")
        print(f"   fk_field     : {r.fk_field}")
        print(f"   related_field: {r.related_field}")
        print(f"   select       : {r.select}")
        print(f"   where        : {r.where}")
        print(f"   order_by     : {r.order_by}")
        print(f"   order_by_dir : {r.order_by_direction}")
        print(f"   alias        : {r.alias}")

    def clone(self):
        return copy.deepcopy(self)

    @property
    def model_table(self):
        return self.model._meta.db_table

    def field_reference(self, field_model):
        return f"{self.related_table}.{self.related_field}"

    def is_model(self, model):
        """Decide if model is equal to self's model."""
        if model is None:
            self.dump()
            raise Exception("Model is None")
        return model_path(model) == model_path(self.model)

    @property
    def join_operator(self):
        if self.join_type:
            return JoinRelation.JOIN_TYPES[self.join_type]
        return "LEFT JOIN"

    @property
    def join_condition_expression(self):
        """Return a str that is the join expression."""
        s = ""

        if hasattr(self.fk_field, "related_fields"):
            for related_fields in self.fk_field.related_fields:

                if s:
                    s += " AND "
                fk = related_fields[0]
                f = related_fields[1]
                s += f'"{fk.model._meta.db_table}"."{fk.column}" = "{f.model._meta.db_table}"."{f.column}"'
        elif isinstance(self.fk_field, ManyToOneRel):
            fk = self.fk_field
            for f_from, f_to in fk.get_joining_columns():
                if s:
                    s += " AND "
                s += f'"{self.alias or fk.model._meta.db_table}"."{f_from}" = "{fk.related_model._meta.db_table}"."{f_to}"'
        elif isinstance(self.fk_field, ManyToManyField):

            pass
        else:
            m = f"""
            op:          {self.join_operator}
            model:       {self.model_table}
            fk_field:    {self.fk_field}
            fk_relation: {self.fk_relation}
            """
            raise Exception(f"Could not find 'related_fields' in 'self.fk_field':  {m}")

        return f"({s})"

    def group_by_columns(self):
        """Return str of GROUP BY columns."""
        grouping = []

        for c in self.column_expressions:
            if not self.xquery.is_aggregate_expression(c):
                grouping.append(c)
        return ", ".join(set(grouping))

    def __str__(self):
        return f"Relation: {model_path(self.model)}"

    def __repr__(self):
        return f"<{self.__class__.__name__}>: {model_path(self.model)}"
