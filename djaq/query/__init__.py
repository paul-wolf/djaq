from typing import Dict, Optional, Union, List
import dataclasses
import csv
import io
import json
import re
import ast
from ast import AST, iter_fields
import logging
import functools
import dataclasses
from django.db import connections, models
from django.db.models.query import QuerySet

from django.utils.text import slugify
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.fields.related import ManyToOneRel, ManyToManyField
from django.core.exceptions import FieldDoesNotExist

from djaq.result import DQResult
from ..astpp import parseprint, dump as node_string
from ..app_utils import (
    get_model_details,
    get_model_classes,
    find_model_class,
    model_path,
    get_schema,
    get_model_from_table,
    get_field_from_model,
    make_dataclass,
    dataclass_mapper,
)
from ..functions import function_whitelist
from djaq.exceptions import UnknownFunctionException
from djaq.conditions import B

import ipdb

# from djaq import app_utils

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERN = re.compile(r"\{([\w]*)\}")

@functools.lru_cache()
def func_in_whitelist(funcname):
    return funcname.lower() in function_whitelist

def concat(funcname, args):
    """Return args spliced by sql concat operator."""
    return " || ".join(args)

def cast(funcname, args):
    t = args[1].replace("'", "").replace("'", "")
    r = f"{args[0]}::{t}"
    return r


def index_choice0(funcname, args):
    """
    index_choice(status, "live", "not-live", "decommissioned")
    """

    index = args.pop(0)
    s = f"CASE {index} "
    for i, a in enumerate(args):
        s += f"WHEN {i} THEN {a} "
    s += "END"
    return s

djaq_functions = {
        "IIF": "CASE WHEN {} THEN {} ELSE {} END",
        "LIKE": "{} LIKE {}",
        "ILIKE": "{} ILIKE {}",
        "CONTAINS": "{} ILIKE %{}%",
        "REGEX": "{} ~ {}",
        "CONCAT": concat,
        "TODAY": "CURRENT_DATE",
        "CAST": cast,
        "POINTX": "ST_X({})",
        "POINTY": "ST_Y({})",
        "INDEX_CHOICE0": index_choice0,
        "COUNTDISTINCT": "COUNT(DISTINCT {})",
        "SUMIF": "SUM(CASE WHEN {} THEN {} ELSE {} END)",
    }
   

def has_context(expression: str, context: dict):
    """We check if the varname
    1. Is in the context
    2. And is not empty
    Empty means either zero length or None
    """

    if not context:
        return True

    m = re.search(PLACEHOLDER_PATTERN, expression)
    if not m:
        return True
    varname = m.group(1)
    value = context.get(varname, None)
    if isinstance(value, (int, float, bool)):
        # we accept 0 and 0.0, False/True as having context
        return True
    # we need this because django response has lists as single values
    # so, you get '[""]' for empty values
    if isinstance(value, (list, tuple)):
        return any(value)
    # otherwise probably a string has context if not zero length or None
    return bool(value)


def render_conditions(node, ctx) -> str:
    """Produce a string repesenting all expressions
    in the node tree as a single expression.
    If a B() node expression references a parameter,
    '$(somevariable)', we check if the context can supply that variable.
    if not we drop that node from the final expression.
    """
    if isinstance(node, str):
        return node if has_context(node, ctx) else ""
    elif isinstance(node, list):
        expressions = [render_conditions(n, ctx) for n in node]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = " and ".join(expressions)
        return f"({s})"
    elif isinstance(node.x, str):
        return node.x if has_context(node.x, ctx) else ""
    elif isinstance(node.x, list):
        expressions = [render_conditions(n, ctx) for n in node.x]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = f" {node.conjunction} ".join(expressions)
        return f"({s})"
    raise Exception(f"Received unexpected type: {type(node)}")


class ContextValidator(object):
    """Base class for validating context data.

    We assume context data is set before parsing.

    """

    def __init__(self, dq, context):
        self.data = context
        self.dq = dq

    def get(self, key, value):
        """Get the value for key.

        Override this method to clean,
        throw exceptions, cast, etc. for a specific value

        """
        return value

    def context(self):
        """Copy the context data.

        Override this to customise context data processing.

        """
        d = {}
        for k, v in self.data.items():
            # psycopg2 wants tuples or else it assumes ARRAY
            if isinstance(v, list):
                v = tuple(v)
            d[k] = self.get(k, v)
        return d


class JoinRelation(object):
    JOIN_TYPES = {"->": "LEFT JOIN", "<-": "RIGHT JOIN", "<>": "INNER JOIN"}

    def __init__(
        self,
        model,
        xquery,
        fk_relation=None,
        fk_field=None,
        related_field=None,
        join_type="->",
        alias=None,
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


class ExpressionParser(ast.NodeVisitor):

    # keep a record of named instances

    directory = {}

    aggregate_functions = {
        "unknown": ["avg", "count", "max", "min", "sum"],
        "sqlite": ["avg", "count", "group_concat", "max", "min", "sum", "total"],
        "postgresql": ["avg", "count", "max", "min", "sum", "stddev", "variance"],
    }

    def find_relation_from_alias(self, alias):
        for relation in self.relations:
            if alias == relation.alias:
                return relation

    def is_aggregate_expression(self, exp):
        """Return True if exp is an aggregate expression like
        `avg(Book.price+Book.price*0.2)`
        """
        s = exp.lower().strip("(").split("(")[0]
        return s in self.vendor_aggregate_functions

    # the ExpressionParser init()
    def __init__(
        self,
        model=None,  # django model  or string of model
        select_src=None,
        where_src=None,
        order_by_src=None,
        using="default",
        limit=None,
        offset=None,
        order_by=None,
        name=None,
        context=None,
        names=None,
        verbosity=0,
        whitelist=None,
        local=False,
    ):
        # main relation
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
        self.dest = ""
        self.using = using
        self.connection = connections[using]
        self.vendor = self.connection.vendor
        self.whitelist = whitelist
        self.verbosity = verbosity
        self.relation_index = 0  # this is the relation being parsed currently
        # self.source = source
        self._limit = limit
        self._offset = offset
        # self.order_by = order_by
        self.sql = None
        self.cursor = None
        self.col_names = None
        self.code = ""
        self.stack = list()
        self.names = list()
        self.column_expressions = list()
        self.relations = list()
        self.parsed = False
        self.expression_context = "select"  # change to 'where' or 'func' later
        self.function_context = ""
        self.fstack = list()  # function stack
        self.parameters = list()  # query parameters
        self.where_marker = 0
        self.context_validator_class = ContextValidator
        self.local = local
        self.unary_stack = list()
        # this tracks when to aggregate a relation potentially before the relations exist
        self.deferred_aggregations = list()
        self.distinct = False
        
        self.add_relation(model=self.model)

        # a set of conditions defined by B nodes
        self.condition_node: Optional[B] = None

        if self.vendor in self.__class__.aggregate_functions:
            self.vendor_aggregate_functions = self.__class__.aggregate_functions[
                self.vendor
            ]
        else:
            self.vendor_aggregate_functions = self.__class__.aggregate_functions[
                "unknown"
            ]
        self.column_headers = list()

    def mogrify(self, sql, parameters):
        """Create completed sql with list of parameters.

        TODO: Only works for Postgresql.

        """

        conn = connections[self.using]
        cursor = conn.cursor()
        return cursor.mogrify(sql, parameters).decode()

    def dump(self):
        for k, v in self.__dict__.items():
            print(f"{k}={v}")

    def conditions(self, node: B):
        self.condition_node = node
        return self

    def aggregate(self):
        """Indicate that the current relation requires aggregation."""
        self.deferred_aggregations.append(self.relation_index)
        # self.relations[self.relation_index].group_by = True

    def add_relation(
        self,
        model,
        fk_relation=None,
        fk_field=None,
        related_field=None,
        join_type="->",
        alias=None,
        field_name=None,
    ):
        """Add relation. Don't add twice unless with different alias.

        model: model class
        fk_relation: an existing relation joining to us
        fk_field: the field of fk_relation used to join us
        related_field: model's field used for the join
        join_type: kind of join, left, right, inner
        alias: alias for the relation

        """

        for relation in self.relations:
            if relation.is_model(model):
                if alias and relation.alias:
                    if alias == relation.alias:
                        return relation
                    else:
                        # this means we have two different aliases
                        # let a new relation be created
                        pass
                else:
                    if alias:
                        relation.alias = alias
                    return relation

        relation = JoinRelation(
            model, self, fk_relation, fk_field, related_field, join_type, alias
        )
        self.relations.append(relation)

        if len(self.relations) > 1 and not relation.fk_field:
            # we need to find out how we are related to existing relations
            for _, rel in enumerate(self.relations):
                for f in rel.model._meta.get_fields():
                    if f.related_model == relation.model:

                        # there can be more than one field related to this model
                        # pick the one that caused us to come here
                        if field_name and not f.name == field_name:
                            continue
                        relation.fk_relation = rel
                        relation.fk_field = f
                        break
                if relation.fk_relation:
                    break
        return relation

    def field_specific_attribute(self, field, relation, attribute_list):
        """
        Return the column expression.
        
        """
        attr = attribute_list.pop()
        if field.get_internal_type() == "DateField":
            return f'date_part(\'{attr}\', "{relation.model._meta.db_table}"."{field.column}")'
        elif field.get_internal_type() == "DateTimeField":
            return f'date_part(\'{attr}\', "{relation.model._meta.db_table}"."{field.column}")'

    def push_attribute_relations(self, attribute_list, relation=None):
        """Return field to represent in context expression.

        Append new relation to self.relations as required.

        We receive this:

            ['name', 'publisher', 'Book']

        """

        # last element must be a field name
        try:
            attr = attribute_list.pop()
        except IndexError:
            # this happens when we are finished
            if not relation:
                relation = self.add_relation(model=self.model)
            return self.push_attribute_relations(attribute_list, relation)

        if relation and not len(attribute_list):
            # attr is the terminal attribute
            field = relation.model._meta.get_field(attr)
            a = f'"{relation.model._meta.db_table}"."{field.column}"'
            return a
        elif not relation and not len(attribute_list):
            # attr is a stand-alone name
            if not self.relations:
                relation = self.add_relation(model=self.model)
            model = self.relations[0].model            
            field = model._meta.get_field(attr)
            if field.auto_created and not field.concrete:
                # this field represents probably a reverse relation to a fk in another model
                self.add_relation(model=field.related_model)
                a = f'"{field.related_model._meta.db_table}"."{field.get_joining_columns()[0][1]}"'
            else:
                a = f'"{model._meta.db_table}"."{field.column}"'
            
            return a

        # if relation and attributes in list
        
        # ipdb.set_trace()
        # if no given relation, we want the master relation
        relation = relation if relation else self.relations[0]
        # print(f"{relation=}")
        field = relation.model._meta.get_field(attr)

        if isinstance(field, ManyToManyField):
            link_model = get_model_from_table(field.m2m_db_table())
            fk_field = get_field_from_model(link_model, field.m2m_field_name())
            self.add_relation(model=link_model, fk_relation=relation, fk_field=fk_field)
            fk_field = get_field_from_model(link_model, field.m2m_reverse_field_name())
            attr = attribute_list.pop()
            new_relation = self.add_relation(
                model=field.related_model, fk_field=fk_field
            )
            related_field = get_field_from_model(field.related_model, attr)
            a = f'"{field.related_model._meta.db_table}"."{related_field.column}"'
            return a
        else:
            # is_relation
            # this means attr is a foreign key
            related_model = field.related_model
            #  we do this to check it is in the whitelist
            if related_model:
                find_model_class(related_model._meta.label, whitelist=self.whitelist)
                new_relation = self.add_relation(related_model, field_name=attr)
            else:
                # probably an attribute of the field
                # example: spend_date.year
                # ipdb.set_trace()
                return self.field_specific_attribute(field, relation, attribute_list)

        return self.push_attribute_relations(attribute_list, new_relation)

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

    def emit_select(self, s):
        if not self.relations:
            # no relation created yet
            raise Exception("Trying to emit to relation select when no relations exist")
        self.relations[self.relation_index].select += str(s)
        self.relations[self.relation_index].expression_str += str(s)

    def push_column_expression(self, s):
        self.relations[self.relation_index].column_expressions.append(s)

    def emit_where(self, s):
        self.relations[self.relation_index].where += str(s)

    def emit_order_by(self, s):
        self.relations[self.relation_index].order_by += str(s)
        if self.unary_stack:
            sign = self.unary_stack.pop()
            if sign == "-":
                self.relations[self.relation_index].order_by += " DESC"

    def emit_func(self, s):
        """Write to current argument on the stack of the current function call."""
        self.fstack[-1]["args"][-1] += str(s)

    def emit(self, s):
        if self.expression_context == "select":
            self.emit_select(s)
        elif self.expression_context == "where":
            self.emit_where(s)
        elif self.expression_context == "order_by":
            self.emit_order_by(s)
        elif self.expression_context == "func":
            self.emit_func(s)

    def single_quoted(self, s):
        return f"'{s}'"

    def generic_visit(self, node):
        if not isinstance(node, ast.Load):
            #  parseprint(node)
            pass
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Expr(self, node):
        # Do not emit any parens
        #  because the relation might not have been created yet
        #  self.emit("(")
        ast.NodeVisitor.generic_visit(self, node)
        #  self.emit(")")

    def visit_Name(self, node):
        self.stack.append(node.id)
        column_expression = self.push_attribute_relations(self.stack)
        if self.expression_context == "select":
            self.names.append(column_expression)
        self.emit(column_expression)
        self.stack = []
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Int(self, node):
        self.emit(node.n)
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Num(self, node):
        self.emit(node.n)
        ast.NodeVisitor.generic_visit(self, node)

    def visit_List(self, node):
        """Assume the list has one element, a string,
        that is a Djaq query."""

        src = [s for s in node.elts][0].s
        dq = self.__class__(src)
        sql = dq.parse(outer_scope=self.relations[self.relation_index])
        self.emit(f"({sql})")
        #  ast.NodeVisitor.generic_visit(self, node)
        return

    def visit_Str(self, node):
        s = node.s

        if node.s.strip().upper().startswith("SELECT "):
            # this is a literal sql subquery
            # we only allow this if the user says we
            # are called locally (the default)
            if self.local:
                self.emit(f"({node.s})")
            ast.NodeVisitor.generic_visit(self, node)
            return

        if node.s.strip().startswith("@"):

            # A named DjaqQuery, QuerySet, List
            # get source
            name = node.s[1:]
            obj = self.resolve_name(name)
            if isinstance(obj, self.__class__):
                sql, sql_params = obj.query()
                self.parameters.extend(sql_params)
            elif isinstance(obj, list):
                # TODO: not safe
                # not even type checking is good here since strings
                # can be sql expressions
                if not self.local:
                    raise Exception("Non-local attempt to use literal SQL")
                sql = str(tuple(obj)).strip("(").strip(")")
                
                    
            elif isinstance(obj, QuerySet):
                sql, sql_params = self.queryset_source(obj)
                sql = self.mogrify(sql, sql_params)
            else:
                raise Exception(f"Name not found: {name}")

            self.emit(f"({sql})")
            return

        if "*" in node.s:
            # quite the hack here
            # not recommended
            if self.relations[self.relation_index].where.endswith(" = "):
                s = s.replace("*", "%")
                parts = self.relations[self.relation_index].where.rpartition(" = ")
                self.relations[self.relation_index].where = parts[0] + " LIKE "

        # if node.s preceded by equals
        # replace equals with LIKE (or ilike)
        # and replace start with %
        self.emit(self.single_quoted(s))
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Call(self, node):
        if node.func.id.lower() in self.__class__.aggregate_functions[self.vendor]:
            self.aggregate()

        last_context = self.expression_context
        self.expression_context = "func"
        self.fstack.append({"funcname": node.func.id, "args": []})
        for i, arg in enumerate(node.args):
            self.fstack[-1]["args"].append("")
            ast.NodeVisitor.visit(self, arg)
        self.expression_context = last_context
        fcall = self.fstack.pop()
        funcname = fcall["funcname"].upper()

        # if funcname in self.__class__.functions:
        if funcname in djaq_functions:
            # Fill our custom SQL template with arguments
            t = djaq_functions[funcname]
            if isinstance(t, str):
                self.emit(t.format(*fcall["args"]))
            elif callable(t):
                self.emit(t(funcname, fcall["args"]))
            else:
                raise Exception(f"Cannot mutate function: {funcname}")
        else:

            # check with whitelist of functions
            if not func_in_whitelist(funcname):
                raise UnknownFunctionException(f"Function '{funcname}' not known")

            # Construct the function call with given arguments
            # and expect the underlying db to support this function in upper case
            args = ", ".join(fcall["args"])
            self.emit(f"{funcname}({args})")

    def visit_Add(self, node):
        self.emit(" + ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Sub(self, node):
        self.emit(" - ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_USub(self, node):
        self.unary_stack.append("-")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Gt(self, node):
        self.emit(" > ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Lt(self, node):
        self.emit(" < ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Eq(self, node):
        self.emit(" = ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_NotEq(self, node):
        self.emit(" <> ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_LtE(self, node):
        self.emit(" <= ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_GtE(self, node):
        self.emit(" >= ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Is(self, node):
        self.emit(" IS ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_IsNot(self, node):
        self.emit(" IS NOT ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_In(self, node):
        self.emit(" IN ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_NotIn(self, node):
        self.emit(" NOT IN ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_NotIn(self, node):
        self.emit(" NOT IN ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_BinOp(self, node):
        self.emit("(")
        ast.NodeVisitor.visit(self, node.left)
        ast.NodeVisitor.visit(self, node.op)
        ast.NodeVisitor.visit(self, node.right)
        self.emit(")")

    def visit_NameConstant(self, node):
        if node.value is True:
            self.emit("TRUE")
        elif node.value is False:
            self.emit("FALSE")
        elif node.value is None:
            self.emit("NULL")
        else:
            raise Exception(f"Unknown value: {node.value}")

    def visit_Set(self, node):
        self.emit("{" + node.elts[0].id + "}")

    def visit_Div(self, node):
        self.emit(" / ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Mult(self, node):
        self.emit(" * ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_BoolOp(self, node):
        self.emit("(")
        v = node.values.pop(0)
        while v:
            ast.NodeVisitor.visit(self, v)
            v = node.values.pop(0) if len(node.values) else None
            if v:
                ast.NodeVisitor.visit(self, node.op)
            # check if we have a named parameter
            # if yes, but no context data, drop the condition

        self.emit(")")

    def visit_And(self, node):
        self.where_marker = len(self.relations[self.relation_index].where)
        self.emit(" AND ")

    def visit_Or(self, node):
        self.where_marker = len(self.relations[self.relation_index].where)
        self.emit(" OR ")

    def visit_Tuple(self, node):
        if self.expression_context not in ["select", "order_by"]:
            self.emit("(")
        for i, el in enumerate(node.elts):
            ast.NodeVisitor.visit(self, el)
            exp = self.relations[self.relation_index].expression_str.strip("(")
            self.push_column_expression(exp.strip(", "))
            self.relations[self.relation_index].expression_str = ""
            if not i == len(node.elts) - 1:
                self.emit(", ")
        if self.expression_context not in ["select", "order_by"]:
            self.emit(")")

    def visit_Arguments(self, node):
        self.emit("|")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_args(self, node):
        self.emit("|")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Attribute(self, node):
        logger.debug(node_string(node))
        self.stack.append(node.attr)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Attribute):
                self.visit_Attribute(child)
            elif isinstance(child, ast.Name):
                self.stack.append(child.id)
            else:
                self.visit(child)

        if self.stack:
            column_expression = self.push_attribute_relations(self.stack)
            if self.expression_context == "select":
                self.names.append(column_expression)
            self.emit(column_expression)
        self.stack = []

    def split_relations(self, s):
        """Split string by join operators returning a list."""

        relation_sources = []
        search = None
        offset = 0
        while True:
            search = re.search("->|<-|<>", s[offset:])
            if search:
                relation_sources.append(s[: search.start() + offset].strip())
                s = s[search.start() + offset :]
            else:
                relation_sources.append(s.strip())
                break
            offset = 2
        return relation_sources

    def get_join_type(self, s):
        if s.startswith("->"):
            return 1, "->", s[2:]
        elif s.startswith("<-"):
            return 1, "<-", s[2:]
        elif s.startswith("<>"):
            return 1, "<>", s[2:]
        else:
            return 0, None, s

    def get_col(self, s):
        """Generator for returning column expressions
        potentially with alias decl."""
        i = 0
        in_parens = 0
        col = ""
        while True:
            c = s[i]
            col += c
            if c == "(":
                in_parens += 1
            elif c == ")":
                in_parens -= 1
            if c == "," and not in_parens:
                yield col[:-1].strip()
                col = ""
            i += 1
            if i >= len(s):
                break
        if col:
            yield col.strip()
        return None

    def parse_column_aliases(self, select_src):
        """Return a list of column aliases."""

        if select_src[0] == "(":
            s = select_src[1:-1]
        else:
            s = select_src
        aliases = []
        #  print(f"parse column aliases: {s}")
        for col in self.get_col(s):
            a = col.split(" as ")
            if len(a) == 1:
                aliases.append(
                    (
                        a[0],
                        slugify(a[0].replace(".", "_").replace(" ", "_")).replace(
                            "-", "_"
                        ),
                    )
                )
            elif len(a) == 2:
                aliases.append((a[0], a[1]))
            else:
                raise Exception("Error defining column")

        return aliases

    def parse_source(
        self, select_src=None, where_src=None, order_by_src=None, outer_scope=None
    ):
        """Parse the source components."""

        self.sql = ""

        select_src = select_src.replace("\n", " ")
        column_tuples = self.parse_column_aliases(select_src)
        # self.column_headers.extend([c[1] for c in column_tuples])
        self.column_headers = [c[1] for c in column_tuples]
        transformed_select_src = ", ".join([c[0] for c in column_tuples])
        self.expression_context = "select"
        self.visit(ast.parse(transformed_select_src))

        if where_src:
            self.expression_context = "where"
            self.visit(ast.parse(where_src))

        if order_by_src:
            self.expression_context = "order_by"
            self.visit(ast.parse(order_by_src))

        # need this to group-by where we need grouping
        for relation_index in self.deferred_aggregations:
            self.relations[relation_index].group_by = True

    def build_sql_statement(self, outer_scope=None):
        """Generate the SQL. Assumes source is parsed.

        No model lookups are done here.

        `outerscope` is the relation enclosing us if we are a subquery.

        """

        self.relations.reverse()
        master_relation = self.relations.pop()
        self.relations.reverse()

        if self.verbosity > 2:
            master_relation.dump()

        ## SELECT EXPRESSIONS
        select = master_relation.select

        for r in self.relations:
            if r.select:
                select = f"{select}, {r.select}"

        if self.distinct:
            s = f"SELECT DISTINCT {select} FROM {master_relation.model_table}"
        else:
            s = f"SELECT {select} FROM {master_relation.model_table}"

        ## FROM JOINS
        if not outer_scope:
            for relation in self.relations:
                s += f" {relation.join_operator} {relation.model_table} {relation.alias or ''} ON {relation.join_condition_expression} "

        ## WHERE
        where = ""
        if master_relation.where:
            where += f" WHERE {master_relation.where}"
        for relation in self.relations:
            if relation.where:
                if where:
                    where += " AND "
                else:
                    where += "WHERE "
                where += relation.where
        s += where

        ## GROUP BY
        if master_relation.group_by:
            gb = master_relation.group_by_columns()
            if gb:
                s += f" GROUP BY {gb}"

        ## ORDER BY
        order = ""
        if master_relation.order_by:
            order += f" ORDER BY {master_relation.order_by}"
        for relation in self.relations:
            if relation.order_by:
                if not order:
                    order = " ORDER BY "
                order += relation.order_by
                if relation.order_by_direction:
                    order += " DESC " if relation.order_by_direction == "-" else " ASC "
        s += order

        if self._limit:
            s += f" LIMIT {int(self._limit)}"

        if self._offset:
            s += f" OFFSET {int(self._offset)}"

        # replace variables placeholders to be valid dict placeholders
        s = re.sub(PLACEHOLDER_PATTERN, lambda x: f"%({x.group(1)})s", s)

        self.sql = s
        self.master_relation = master_relation

        return self.sql

    def rewind(self):
        """Rewind cursor by setting to None.
        The next time a generator method is called,
        the query will be executed again.
        """
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
        # ipdb.set_trace()
        
        self.cursor = self.connection.cursor()

        if count:
            sql = f"SELECT COUNT(*) FROM ({sql}) c"

        if len(self._context):
            context = self.context_validator_class(self, self._context).context()
            if self.verbosity:
                conn = connections[self.using]
                cursor = conn.cursor()
                logger.debug(cursor.mogrify(sql, context))
                if self.verbosity:
                    print(f"sql={sql}, params={context}")
            self.cursor.execute(sql, context)
        else:
            if self.verbosity:
                print(f"sql={sql}")
            logger.debug(sql)
            self.cursor.execute(sql)

    def query(self, context=None):
        """Return source for djaqquery and parameters."""
        self.context(context)
        # ipdb.set_trace()
        self.construct()
        sql = self.sql
        return sql, self.parameters

    def where(self, node: Union[str, B]):
        if not node:
            return
        # ipdb.set_trace()
        if isinstance(node, str):
            node = B(node)
        elif isinstance(node, B):
            node = node
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

    def construct(self):
        """Build the final SQL into parser.sql"""
        
        self.where_src = ""
        if self.condition_node:
            if self.where_src:
                self.where_src += " and "
            else:
                self.where_src = ""
            self.where_src += render_conditions(
                self.condition_node, self._context
            )

        self.parse_source(self.select_src, self.where_src, self.order_by_src)

        self.build_sql_statement()


    def dicts(self, data=None):
        if not self.cursor:
            self.execute(data)
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            row_dict = dict(zip(self.column_headers, row))
            yield row_dict
        return

    def tuples(self, data=None, flat=False):
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
        return

    def json(self, data=None, encoder=DjangoJSONEncoder):
        for d in self.dicts(data):
            yield json.dumps(d, cls=encoder)

    def objs(self, data=None):
        if not self.cursor:
            self.execute(data)
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            row_dict = dict(zip(self.column_headers, row))
            yield DQResult(row_dict, dq=self)

    def next(self, data=None):
        if not self.cursor:
            self.execute(data)
        row = self.cursor.fetchone()
        row_dict = dict(zip(self.column_headers, row))
        return DQResult(row_dict, dq=self)

    def csv(self, data=None):
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

    def value(self, data=None):
        for t in self.tuples(data=data):
            return t[0]

    def count(self, data=None):
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


class DjaqQuery:
    def __init__(
        self,
        model_source: Union[models.Model, str],
        select_source: Union[str, List, None] = None,
        name: str = None,
        names: Union[Dict, None] = None,
        whitelist=None,
    ):
        if isinstance(model_source, models.base.ModelBase):
            model = model_source
        elif isinstance(model_source, str):
            model = find_model_class(model_source, whitelist=whitelist)
        else:
            raise Exception(
                f"Type not supported for model source: {type(model_source)}"
            )

        self.parser = ExpressionParser(model=model, whitelist=whitelist, name=name)

        if not select_source or select_source == "*":
            select_source = ", ".join(
                [f for f in get_model_details(model, self.parser.connection)["fields"]]
            )
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

    def construct(self):
        self.parser.construct()

    def order_by(self, source: Union[str, List]):
        self.parser.order_by(source)
        return self

    def where(self, node: Union[str, B]):
        self.parser.where(node)
        return self

    def get(self, pk_value: any):
        """Return a single model instance whose primary key is pk_value."""
        return self.model.objects.get(pk=pk_value)

    def update_object(self, pk_value: any, update_function: callable, data: Dict, save=True):
        obj = self.get(pk_value)
        return update_function(obj, data, save)
        
    def distinct(self):
        self.parser.distinct = True
        return self

    def dicts(self, data=None):
        self.construct()
        return self.parser.dicts(data=data)

    def tuples(self, data=None, flat=False):
        self.construct()
        return self.parser.tuples(data=data, flat=flat)

    def count(self, data=None):
        self.construct()
        return self.parser.count(data)

    def sql(self):
        self.construct()
        return self.parser.sql

    def rewind(self):
        self.parser.rewind()
        return self

    def csv(self, data=None):
        self.construct()
        return self.parser.csv(data)

    def limit(self, limit):
        self.parser._limit = limit
        return self

    def offset(self, offset):
        self.parser._offset = offset
        return self

    def context(self, context: Dict):
        """Update our context with dict context."""
        if not self.parser._context:
            self.parser._context = dict()
        if context:
            self.parser.cursor = None  # cause the query to be re-evaluated
            self.parser._context.update(context)
        return self

    def json(self, data=None, encoder=DjangoJSONEncoder):
        self.construct()
        return self.parser.json(data, encoder)

    def objs(self, data=None):
        self.construct()
        return self.parser.objs(data)

    def value(self, data=None):
        self.construct()
        return self.parser.value(data)

    def dataframe(self, context=None):
        """Return a pandas dataframe.
        This only works if pandas is installed.
        """
        import pandas.io.sql as sqlio
        import pandas as pd

        self.construct()
        self.context(context)
        constructed_sql = self.parser.sql
        sql = self.parser.mogrify(constructed_sql, self.parser._context)
        df = pd.read_sql(sql, self.parser.connection)
        df.columns = self.parser.column_headers
        return df

    def qs(self):
        return self.parser.model.objects.raw(self.sql(), self.parser._context)

    def go(self):
        return list(self.dicts())
    
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

    def __iter__(self):
        return self.dicts()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            pass
        else:
            pass

# class Cursor:
#     def __init__(self, values: Values):
#         self.values = values
#         self.verbosity = values.parser.verbosity
#         self.cursor = None

#     def execute(self, context=None, count=False):
#         """Create a cursor and execute the sql."""

#         self.values.parser.context(context)


#         sql = self.values.parser.parse_values(self.values.aliases)

#         self.cursor = self.values.parser.connection.cursor()

#         if count:
#             sql = f"SELECT COUNT(*) FROM ({sql}) c"
#         if len(self.values.parser._context):
#             context = self.values.parser.context_validator_class(self, self.values.parser._context).context()
#             if self.verbosity:
#                 conn = connections[self.values.parser.using]
#                 cursor = conn.cursor()
#                 logger.debug(cursor.mogrify(sql, context))
#                 if self.verbosity:
#                     print(f"sql={sql}, params={context}")
#             self.cursor.execute(sql, context)
#         else:
#             if self.verbosity:
#                 print(f"sql={sql}")
#             logger.debug(sql)
#             self.cursor.execute(sql)

#     def dicts(self, data=None):
#         if not self.cursor:
#             self.execute(data)
#         while True:
#             row = self.cursor.fetchone()
#             if row is None:
#                 break
#             row_dict = dict(zip(self.values.parser.column_headers, row))
#             yield row_dict
#         return
