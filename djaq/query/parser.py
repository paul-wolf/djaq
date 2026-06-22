import copy
import csv
import io
import json
import re
import ast
from typing import Dict, Optional, Union, List

from django.db import connections, models
from django.db.models.query import QuerySet
from django.utils.text import slugify
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.fields.related import (
    ManyToManyField,
    OneToOneRel,
)

from djaq.result import DQResult
from djaq.exceptions import UnknownFunctionException
from djaq.conditions import B
from ..app_utils import (
    find_model_class,
    get_model_from_table,
    get_field_from_model,
)
from .context import ContextValidator, PLACEHOLDER_PATTERN
from .conditions import render_conditions, render_conditions_drop_empty
from .sql_functions import (
    djaq_functions,
    aggregate_functions,
    func_in_whitelist,
    build_case_statement_from_choices,
)
from .relations import JoinRelation


class ExpressionParser(ast.NodeVisitor):

    # keep a record of named instances

    directory = {}

    def find_relation_from_alias(self, alias):
        for relation in self.relations:
            if alias == relation.alias:
                return relation

    def is_aggregate_expression(self, exp):
        """Return True if exp is an aggregate expression like
        `avg(price+price*0.2)`
        """
        s = exp.lower().strip("(").split("(")[0]
        return s in self.vendor_aggregate_functions

    # the ExpressionParser init()
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
        self.relation_index = 0  # this is the relation being parsed currently
        # self.source = source
        self._limit = limit
        self._offset = offset
        # self.order_by = order_by
        self.sql = None
        self.cursor = None
        self.stack = list()
        self.names: List[str] = list()
        self.column_expressions = list()
        self.relations = list()
        self.expression_context = "select"  # change to 'where' or 'func' later
        self.fstack = list()  # function stack
        self.parameters = list()  # query parameters
        self.context_validator_class = ContextValidator
        self.local = local
        self.unary_stack = list()
        # this tracks when to aggregate a relation potentially before the relations exist
        self.deferred_aggregations = list()
        self.distinct = False
        self.drop_empty = drop_empty

        self.add_relation(model=self.model)

        # a set of conditions defined by B nodes
        self.condition_node: Optional[B] = None

        if self.vendor in aggregate_functions:
            self.vendor_aggregate_functions = aggregate_functions[self.vendor]
        else:
            self.vendor_aggregate_functions = aggregate_functions["unknown"]
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
        p.relations = list()
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
            if attr.lower() == "date":
                return f'DATE("{relation.model._meta.db_table}"."{field.column}")'
            return f'date_part(\'{attr}\', "{relation.model._meta.db_table}"."{field.column}")'

    def push_attribute_relations(self, attribute_list, relation=None):
        """Return field to represent in context expression.

        Append new relation to self.relations as required.

        We receive this:

            ['name', 'publisher']

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
            if attr.endswith("_display"):
                field = relation.model._meta.get_field(attr[:-8])
                field_exp = f'"{relation.model._meta.db_table}"."{field.column}"'
                if field.choices:
                    return build_case_statement_from_choices(field_exp, field.choices)
            field = relation.model._meta.get_field(attr)
            if isinstance(field, OneToOneRel):
                
                # the case if we reference a onetoone but no single field
                raise Exception("Specify a field name in the related model")

            return f'"{relation.model._meta.db_table}"."{field.column}"'
        elif not relation and not len(attribute_list):
            # attr is a stand-alone name
            if not self.relations:
                relation = self.add_relation(model=self.model)
            model = self.relations[0].model

            if attr.endswith("_display"):
                
                field = model._meta.get_field(attr[:-8])
            else:
                field = model._meta.get_field(attr)
            if field.auto_created and not field.concrete:
                # this field represents probably a reverse relation to a fk in another model
                self.add_relation(model=field.related_model)
                return f'"{field.related_model._meta.db_table}"."{field.get_joining_columns()[0][1]}"'
            else:
                field_exp = f'"{model._meta.db_table}"."{field.column}"'
                if attr.endswith("_display") and field.choices:
                    return build_case_statement_from_choices(field_exp, field.choices)
                return field_exp

        # if relation and attributes in list

        
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
                # if obj has _context, we need to inherit that
                self.context(obj._context)
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
        if node.func.id.lower() in aggregate_functions[self.vendor]:
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

    # def visit_NotIn(self, node):
    #     self.emit(" NOT IN ")
    #     ast.NodeVisitor.generic_visit(self, node)

    def visit_Not(self, node):
        self.emit(" NOT ")
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
        self.emit(" AND ")

    def visit_Or(self, node):
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

        self.sql is assigned to

        """

        # self.relations.reverse()
        # master_relation = self.relations.pop()
        # self.relations.reverse()
        master_relation = self.relations[0]

        ## SELECT EXPRESSIONS
        select = master_relation.select

        if len(self.relations) > 1:
            for r in self.relations[1:]:
                if r.select:
                    select = f"{select}, {r.select}"

        if self.distinct:
            s = f"SELECT DISTINCT {select} FROM {master_relation.model_table}"
        else:
            s = f"SELECT {select} FROM {master_relation.model_table}"

        ## FROM JOINS
        if not outer_scope:
            for relation in self.relations[1:]:
                s += f" {relation.join_operator} {relation.model_table} {relation.alias or ''} ON {relation.join_condition_expression} "

        ## WHERE
        where = "\n"
        if master_relation.where:
            where += f" WHERE {master_relation.where}"
        for relation in self.relations[1:]:
            if relation.where:
                if where:
                    where += " AND "
                else:
                    where += "WHERE "
                where += relation.where
        s += where + "\n"

        ## GROUP BY
        if master_relation.group_by:
            gb = master_relation.group_by_columns()
            if gb:
                s += f" GROUP BY {gb}"

        ## ORDER BY
        order = ""
        if master_relation.order_by:
            order += f" ORDER BY {master_relation.order_by}"
        for relation in self.relations[1:]:
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

    def construct(self):
        """Build the final SQL into parser.sql"""
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
        # need to completely rebuild
        self.relations = list()
        self.add_relation(model=self.model)
        self.parse_source(self.select_src, src, self.order_by_src)
        self.build_sql_statement()

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
