import csv
import io
import json
import re
import ast
from ast import AST, iter_fields, parse
from collections import defaultdict
import uuid

import psycopg2
from psycopg2.extras import DictCursor

import django
from django.db import connections, models
from django.db.models.query import QuerySet
# from django.db.models.sql import UpdateQuery
from django.utils.text import slugify
from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings

from .result import DQResult
from .astpp import parseprint
from .app_utils import model_field, find_model_class, model_path


class DjangoQuery(ast.NodeVisitor):

    # keep a record of named instances
    
    directory = {}
    functions = {
        "IIF": "CASE WHEN {} THEN {} ELSE {} END",
        "LIKE": "{} LIKE {}",
        "ILIKE": "{} ILIKE {}",
        "REGEX": "{} ~ {}",
    }
    
    aggregate_functions = {
        "unknown": [
            'avg',
            'count',
            'max',
            'min',
            'sum',
        ],
        "sqlite": [
            'avg',
            'count',
            'group_concat',
            'max',
            'min',
            'sum',
            'total',
        ],
        "postgresql": [
            'avg',
            'count',
            'max',
            'min',
            'sum',
            'stddev',
            'variance',
        ],
    }

    class JoinRelation(object):
        JOIN_TYPES = {
            "->": "LEFT JOIN",
            "<-": "RIGHT JOIN",
            "<>": "INNER JOIN",
        }

        def __init__(self,
                     model,
                     xquery,
                     fk_relation=None,
                     fk_field=None,
                     related_field=None,
                     join_type='->',
                     alias=None):
            self.model = model
            self.fk_relation = fk_relation
            self.fk_field = fk_field
            self.related_field = related_field
            self.join_type = join_type  # left, right, inner
            self.alias = alias
            self.select = ''
            self.expression_str = ''
            self.column_expressions = []
            self.where = ''
            self.group_by = False
            self.order_by = ''
            self.order_by_direction = '+'
            self.xquery = xquery
            self.src = None

        def dump(self):
            r = self
            print("   join         : {}".format(r.join_type))
            print("   fk_relation  : {}".format(r.fk_relation))
            print("   fk_field     : {}".format(r.fk_field))
            print("   related_field: {}".format(r.related_field))
            print("   select       : {}".format(r.select))
            print("   where        : {}".format(r.where))
            print("   order_by     : {}".format(r.order_by))
            print("   order_by_dir : {}".format(r.order_by_direction))
            print("   alias        : {}".format(r.alias))
            
        @property
        def model_table(self):
            return self.model._meta.db_table

        def field_reference(self, field_model):
            return "{}.{}".format(self.related_table, self.related_field)

        def is_model(self, model):
            """Decide if model is equal to self's model."""
            return model_path(model) == model_path(self.model)

        @property
        def join_operator(self):
            if self.join_type:
                return self.xquery.__class__.JoinRelation.JOIN_TYPES[self.join_type]
            return 'LEFT JOIN'

        @property
        def join_condition_expression(self):
            s = ''

            # print(self.fk_field.related_fields)
            for related_fields in self.fk_field.related_fields:
                # print("related_fields")
                # print(related_fields)
                if s:
                    s += " AND "
                fk = related_fields[0]
                f = related_fields[1]
                s += '{}.{} = {}.{}'.format(fk.model._meta.db_table, fk.column,
                                            f.model._meta.db_table, f.column)
            return "({})".format(s)

        def group_by_columns(self):
            """Return str of GROUP BY columns."""
            grouping = []

            for c in self.column_expressions:
                if not self.xquery.is_aggregate_expression(c):
                    grouping.append(c)
            return ", ".join(set(grouping))

        def __str__(self):
            return "Relation: {}".format(model_path(self.model))

    def find_relation_from_alias(self, alias):
        for relation in self.relations:
            if alias == relation.alias:
                return relation

    def is_aggregate_expression(self, exp):
        """Return True if exp is an aggregate expression like 
        `avg(Book.price+Book.price*0.2)`"""
        s = exp.lower().strip("(").split("(")[0]
        return s in self.vendor_aggregate_functions

    def __init__(self,
                 source,
                 using='default',
                 limit=None,
                 offset=None,
                 order_by=None,
                 name=None,
                 context=None,
                 names=None,
                 verbosity=0):

        self._context = context
        
        if name:
            self.__class__.directory[name] = self

        # these can be names of other objects
        if names:
            self.__class__.directory.update(names)

        self.using = using
        self.connection = connections[using]
        self.vendor = self.connection.vendor

        self.verbosity = verbosity
        self.relation_index = 0  # this is the relation being parsed currently
        self.source = source
        self._limit = limit
        self._offset = offset
        self.order_by = order_by
        self.sql = None
        self.cursor = None
        self.col_names = None
        self.relations = []
        self.code = ''
        self.stack = []
        self.names = []
        self.column_expressions = []
        self.relations = []
        self.parsed = False
        self.expression_context = 'select'  # change to 'where' or 'func' later
        self.function_context = ''
        self.fstack = []  # function stack
        self.parameters = []  # query parameters
            
        
        # self.group_by = False
        if self.vendor in self.__class__.aggregate_functions:
            self.vendor_aggregate_functions = self.__class__.aggregate_functions[
                self.vendor]
        else:
            self.vendor_aggregate_functions = self.__class__.aggregate_functions[
                'unknown']
        self.column_headers = []

    def mogrify(self, sql, parameters):
        """Create completed sql with list of parameters.

        TODO: Only works for Postgresql.

        """
        
        conn = connections[self.using]
        cursor = conn.cursor()
        return cursor.mogrify(sql, parameters).decode()
        
    def dump(self):
        for k, v in self.__dict__.items():
            print("{}={}".format(k,v))
            
    def aggregate(self):
        """Indicate that the current relation requires aggregation."""
        # print("Setting group by: {}".format(self.relations[self.relation_index]))
        self.relations[self.relation_index].group_by = True

    def add_relation(self,
                     model,
                     fk_relation=None,
                     fk_field=None,
                     related_field=None,
                     join_type='->',
                     alias=None):
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

        relation = self.__class__.JoinRelation(model, self, fk_relation, fk_field,
                                       related_field, join_type, alias)
        self.relations.append(relation)

        if len(self.relations) > 1:
            # we need to find out how we are related to existing relations
            for i, rel in enumerate(self.relations):
                for f in rel.model._meta.get_fields():
                    if f.related_model == relation.model:
                        relation.fk_relation = rel
                        relation.fk_field = f
                        break
                if relation.fk_relation:
                    break
        return relation

    def push_attribute_relations(self, attribute_list, relation=None):
        """Return field to represent in context expression.

        Append new relation to self.relations as required.

        We receive this:

            ['name', 'publisher', 'Book']

        """

        # print("attribute list: {}".format(attribute_list))
        # print("relation      : {}".format(relation))
        # input("press key 11111")

        # last element must be a field name
        attr = attribute_list.pop()

        # print("attr          : {}".format(attr))
        # print("attribute list: {}".format(attribute_list))
        # print("relation      : {}".format(relation))
        # input("press key 22222")

        if relation and not len(attribute_list):
            # attr is the terminal attribute
            field = relation.model._meta.get_field(attr)
            return "{}.{}".format(relation.model._meta.db_table, field.column)
        elif not relation and not len(attribute_list):
            # attr is a stand-alone name
            model = self.relations[-1].model
            field = model._meta.get_field(attr)
            return "{}.{}".format(model._meta.db_table, field.column)
        elif not relation and len(attribute_list):
            # this happens when we have something like 'Book.name'
            # therefore attr must be a model name or alias
            relation = self.find_relation_from_alias(attr)
            if not relation:
                model = find_model_class(attr)
                relation = self.add_relation(model=model)
            return self.push_attribute_relations(attribute_list, relation)

        # print("*"*66)
        # print(attribute_list)
        # input("press key 33333")

        # if relation and attributes in list
        # this means attr is a foreign key
        model = relation.model._meta.get_field(attr).related_model
        relation = self.add_relation(model)
        return self.push_attribute_relations(attribute_list, relation)

    def resolve_name(self, name):
        if name in self.__class__.directory:
            return self.__class__.directory[name]
        # check locals, globals
        else:
            # TODO: throw exception
            return None

    def queryset_source(self, queryset):
        sql, sql_params = queryset.query.get_compiler(
            connection=self.connection).as_sql()
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

    def emit_func(self, s):
        """Write to current argument on the stack of the current function call."""
        self.fstack[-1]['args'][-1] += str(s)

    def emit(self, s):
        if self.expression_context == 'select':
            self.emit_select(s)
        elif self.expression_context == 'where':
            self.emit_where(s)
        elif self.expression_context == 'order_by':
            self.emit_order_by(s)
        elif self.expression_context == 'func':
            self.emit_func(s)

    def single_quoted(self, s):
        return "'{}'".format(s)

    def generic_visit(self, node):
        if not isinstance(node, ast.Load):
            # parseprint(node)
            pass
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Expr(self, node):
        # Do not emit any parens yet
        # because the relation might not have been created yet
        # self.emit("(")
        ast.NodeVisitor.generic_visit(self, node)
        # self.emit(")")
        
    def visit_Name(self, node):
        self.stack.append(node.id)
        column_expression = self.push_attribute_relations(self.stack)
        if self.expression_context == 'select':
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

    def visit_Str(self, node):
        s = node.s

        if node.s.strip().upper().startswith("SELECT "):
            # this is a literal sql subquery
            self.emit("({})".format(node.s))
            ast.NodeVisitor.generic_visit(self, node)
            return

        if node.s.strip().startswith('@'):

            # A named DjangoQuery, QuerySet, List
            # get source
            name = node.s[1:]
            obj = self.resolve_name(name)
            if isinstance(obj, self.__class__):
                sql, sql_params = obj.query()
                self.parameters.extend(sql_params)
            elif isinstance(obj, list):
                # TODO: not really safe
                # not even type checking is good here since strings
                # can be query expressions
                sql = str(tuple(obj)).strip('(').strip(')')
            elif isinstance(obj, QuerySet):
                sql, sql_params = self.queryset_source(obj)
                sql = self.mogrify(sql, sql_params)
            else:
                raise Exception("Name not found: {}".format(name))

            self.emit("({})".format(sql))
            return

        if "*" in node.s:
            # quite the hack here
            # not recommended
            if self.relations[self.relation_index].where.endswith(' = '):
                s = s.replace("*", "%")
                parts = self.relations[self.relation_index].where.rpartition(
                    ' = ')
                self.relations[self.relation_index].where = parts[0] + ' LIKE '

        # if node.s preceded by equals
        # replace equals with LIKE (or ilike)
        # and replace start with %
        self.emit(self.single_quoted(s))
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Call(self, node):
        if node.func.id.lower() in self.__class__.aggregate_functions[self.vendor]:
            self.aggregate()

        last_context = self.expression_context
        self.expression_context = 'func'
        self.fstack.append({'funcname': node.func.id, 'args': []})
        for i, arg in enumerate(node.args):
            self.fstack[-1]['args'].append('')
            ast.NodeVisitor.visit(self, arg)
        self.expression_context = last_context
        fcall = self.fstack.pop()
        funcname = fcall['funcname'].upper()
        if funcname in self.__class__.functions:
            # Fill our custom SQL template with arguments
            t = self.__class__.functions[funcname]
            if isinstance(t, str):
                self.emit(t.format(*fcall['args']))
            elif callable(t):
                self.emit(t(funcname, fcall['args']))
            else:
                raise Exception("Can't mutate function: {}".format(funcname))
        else:
            # Construct the function call with given arguments
            # and expect the underlying db to support this function in upper case
            self.emit("{}({})".format(fcall['funcname'],
                                      ", ".join(fcall['args'])))

    def visit_Add(self, node):
        self.emit(" + ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Sub(self, node):
        self.emit(" - ")
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

    def visit_BinOp(self, node):
        self.emit("(")
        ast.NodeVisitor.visit(self, node.left)
        ast.NodeVisitor.visit(self, node.op)
        ast.NodeVisitor.visit(self, node.right)
        self.emit(")")

    def visit_Div(self, node):
        self.emit(" / ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Mult(self, node):
        self.emit(" * ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_BoolOp(self, node):
        # parseprint(node)
        self.emit("(")
        v = node.values.pop(0)
        while v:
            ast.NodeVisitor.visit(self, v)
            v = node.values.pop(0) if len(node.values) else None
            if v:
                ast.NodeVisitor.visit(self, node.op)
        self.emit(")")
        
    def visit_And(self, node):
        self.emit(" AND ")

    def visit_Or(self, node):
        self.emit(" OR ")        

    def visit_Tuple(self, node):
        for i, el in enumerate(node.elts):
            # print("v"*66)
            # parseprint(el)

            ast.NodeVisitor.visit(self, el)
            exp = self.relations[self.relation_index].expression_str.strip('(')
            self.push_column_expression(exp.strip(', '))
            self.relations[self.relation_index].expression_str = ''

            if not i == len(node.elts) - 1:
                self.emit(", ")

    def visit_Arguments(self, node):
        self.emit('|')
        ast.NodeVisitor.generic_visit(self, node)

    def visit_args(self, node):
        self.emit('|')
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
            if self.expression_context == 'select':
                self.names.append(column_expression)
            self.emit(column_expression)
        self.stack = []

    def split_relations(self, s):
        """Split string by join operators returning a list."""

        relation_sources = []
        search = None
        offset = 0
        while True:
            # print("SEARCHING: {}, offset={}".format(s, offset))
            search = re.search("->|<-|<>", s[offset:])

            if search:
                relation_sources.append(s[:search.start() + offset].strip())
                # print("FOUND: {}, start={}".format(s[:search.start()+offset], search.start()))
                s = s[search.start() + offset:]
                # print("REDUCED: {}".format(s))
            else:
                relation_sources.append(s.strip())
                # print("LAST: {}".format(s))
                break

            offset = 2
            # input("Press Enter to continue...")

        return relation_sources

    def get_join_type(self, s):
        if s.startswith("->"):
            return 1, '->', s[2:]
        elif s.startswith("<-"):
            return 1, '<-', s[2:]
        elif s.startswith("<>"):
            return 1, '<>', s[2:]
        else:
            return 0, None, s
        
    def get_select(self, s):
        """Get select string.
        Return string once parens are balanced.
        First character needs to be an opening parens.
        """
        i = 0
        in_parens = 0
        select = ''
        for i, c in enumerate(s):
            select += c
            if c == '(':
                in_parens += 1
            elif c == ')':
                in_parens -= 1
            if not in_parens:
                return i, select, s[i+1:]
            
    
    def get_col(self, s):
        """Generator for returning column expressions 
        potentially with alias decl."""
        i = 0
        in_parens = 0
        col = ''
        while True:
            c = s[i]
            col += c
            if c == '(':
                in_parens += 1
            elif c == ')':
                in_parens -= 1
            if c == "," and not in_parens:
                yield col[:-1].strip()
                col = ''
            i += 1
            if i >= len(s):
                break
        if col:
            yield col.strip()
        return None

    def parse_column_aliases(self, select_src):
        pattern = "\(.*?\)|(,)"
        # assume parens, remove them
        if select_src[0] == "(":
            s = select_src[1:-1]
        else:
            s = select_src
        aliases = []
        # print("parse column aliases: {}".format(s))
        m = True
        for col in self.get_col(s):
            a = col.split(" as ")
            if len(a) == 1:
                aliases.append((a[0],
                                slugify(a[0].replace(".", "_").replace(
                                    " ", "_")).replace("-", "_")))
            elif len(a) == 2:
                aliases.append((a[0], a[1]))
            else:
                raise Exception("Error defining column")

        return aliases

    def parse(self):
        """Parse source.

        """

        if self.sql:
            return self.sql

        pattern = "([\w]+)[\s]*(\{.*\})?\s*([\w]+)?\s*(order_by|order by)?\s*(\+|\-)?(\(.*\))?"
        """
        We get a relation string like this: 
        
        ->(Book.name as title, Book.publisher.name as pub, count()) Book{length(b.name) > 50)} b  

        group 1: model
        group 2: filter
        group 3: alias
        group 4: order by
        group 5: order by direction
        group 6: order_by_src
        """
        self.source = self.source.replace('\n', ' ')
        relation_sources = self.split_relations(self.source)
        # print("relation_sources: {}".format(relation_sources))

        for i, relation_source in enumerate(relation_sources):
            # print("Parsing relation: {}".format(relation_source))
            index, join_type, relation_source = self.get_join_type(relation_source)            
            index, select_src, relation_source = self.get_select(relation_source)
            # print(relation_source)
            m = re.match(pattern, relation_source.strip())
            if m:
                model_name = m.group(1)
                where_src = m.group(2)
                alias = m.group(3) if m.group(3) else model_name
                order_by_direction = m.group(5)
                order_by_src = m.group(6)

            elif re.match("^(\(.*\))$", self.source):
                join_type = None
                # strip whitespace
                src = self.source.strip()
                if src[0] == "(":
                    src = src[1:-1]
                select_src = src.strip()
                model_name = None
                where_src = None
                order_by_src = None
                order_by_direction = None
                alias = None
            else:
                raise Exception("Invalid source")

            if self.verbosity > 1:
                print(
                    "join_type={}, select_src={}, model_name={}, where_src={}, order_by_src={}, order_by_direction={}, alias={}"
                    .format(join_type, select_src, model_name, where_src,
                            order_by_src, order_by_direction, alias))

            # we need to generate column headers and remove
            # aliases. tuples are (exp, alias)
            column_tuples = self.parse_column_aliases(select_src)
            self.column_headers = [c[1] for c in column_tuples]
            select_src = ", ".join([c[0] for c in column_tuples])
            relation = self.find_relation_from_alias(alias)
            model = find_model_class(model_name)
            if model and not relation:
                relation = self.add_relation(model=model, alias=alias)
                # print("Created JoinRelation: {}".format(relation))
            else:
                if self.verbosity > 2:
                    print("Relation already existed: {}".format(relation))
            self.relation_index = i

            if select_src:
                if select_src.upper().startswith("'(SELECT "):
                    relation.src = select_src
                else:
                    self.expression_context = 'select'
                    self.visit(ast.parse(select_src))

            if self.verbosity > 2 or len(self.relations) == 0:
                print("relation index {}:".format(i))
                print("\trelation_source={}".format(relation_source))
                print("\tjoin_type={}".format(join_type))
                print("\tselect_src={}".format(select_src))
                print("\tmodel_name={}".format(model_name))
                print("\twhere_src={}".format(where_src))
                print("\talias={}".format(alias))
                print("\torder_by_direction={}".format(order_by_direction))
                print("\torder_by_src={}".format(order_by_src))
                self.dump()


            if not relation:
                relation = self.relations[-1]
            relation.order_by_direction = order_by_direction

            if where_src:
                self.expression_context = 'where'
                self.visit(ast.parse(where_src))

            if order_by_src:
                self.expression_context = 'order_by'
                self.visit(ast.parse(order_by_src))

        if self.verbosity > 2:
            print("Database vendor: {}".format(self.vendor))

        if self.verbosity > 1:
            for r in self.relations:
                print("Relation        : {}".format(str(r)))
                r.dump()

        self.relations.reverse()

        master_relation = self.relations.pop()
        if self.verbosity > 2:
            master_relation.dump()
            
        s = "SELECT {} FROM {}".format(master_relation.select,
                                       master_relation.model_table)
        for i, relation in enumerate(self.relations):
            s += " {} {} ON {} ".format(relation.join_operator,
                                        relation.model_table,
                                        relation.join_condition_expression)
            if relation.where:
                s += " WHERE {}".format(relation.where)
            if relation.order_by:
                s += " ORDER BY {}".format(relation.order_by)
                if relation.order_by_direction == '-':
                    s += ' DESC'
        if master_relation.where:
            s += " WHERE {}".format(master_relation.where)
        if master_relation.group_by:
            gb = master_relation.group_by_columns()
            if gb:
                s += " GROUP BY {}".format(gb)
        if master_relation.order_by:
            s += " ORDER BY {}".format(master_relation.order_by)
            if master_relation.order_by_direction == '-':
                s += ' DESC'
        if self._limit:
            s += " LIMIT {}".format(int(self._limit))
        if self._offset:
            s += " OFFSET {}".format(int(self._offset))
        self.sql = s
        return self.sql

    def query(self, context=None):
        """Return source for djangoquery and parameters.

        """

        self.context(context)
        
        sql = self.parse()
        if self.verbosity > 0:
            print(sql)
        sql = sql.replace("'%s'", "%s")
        return sql, self.parameters

    def rewind(self):
        """Rewind cursor.

        Full re-execution of query!
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
            self.cursor = None # cause the query to be re-evaluated
            self._context.update(context)
        return self
    
        
    def pg_cursor(self, using=None):
        """

        'dbname=test user=postgres password=secret'

        dbname – the database name (database is a deprecated alias)
        user – user name used to authenticate
        password – password used to authenticate
        host – database host address (defaults to UNIX socket if not provided)
        port – connection port number (defaults to 5432 if not provided)
        """

        using = using if using else self.using

        data = {}
        data['name'] = settings.DATABASES[using]['NAME']
        data['user'] = settings.DATABASES[using]['USER']
        if 'PASSWORD' in settings.DATABASES[using]:
            data['password'] = settings.DATABASES[using]['PASSWORD']
        dsn = "dbname={name} user={user} password={password}".format(**data)
        dsn = "dbname={name} user={user}".format(**data)
        conn = psycopg2.connect(dsn)
        cursor_name = uuid.uuid4().hex
        cursor = conn.cursor(cursor_name)
        cursor.itersize = 100
        return cursor

    
    def execute(self, context=None, count=False):
        """Create a cursor and execute the sql."""

        self.context(context)
            
        sql = self.parse()
        
        # sql = sql.replace("'%s'", "%s")

        # now replace variables placeholders to be valid dict placeholders
        p = re.compile(r"\'\$\(([\w]*)\)\'")
        sql = re.sub(p, lambda x: "%({})s".format(x.group(1)), sql)

        # print("vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
        # print(sql)
        conn = connections[self.using]
        cursor = conn.cursor()
        # print(cursor.mogrify(sql, self._context))
        # print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")

        self.cursor = self.connection.cursor()

        try:
            if count:
                sql = "SELECT COUNT(*) FROM ({}) c".format(sql)
            if len(self._context):
                if self.verbosity:
                    print("sql={}, params={}".format(sql, self._context))
                self.cursor.execute(sql, self._context)
            else: 
                if self.verbosity:
                    print("sql={}".format(sql))
                self.cursor.execute(sql)
        except django.db.utils.ProgrammingError as dbe:
            print(dbe)
        except psycopg2.ProgrammingError as pe:
            print(pe)

        # we record the column names from the cursor
        # but we have our own aliases in self.column_headers
        # self.col_names = [desc[0] for desc in self.cursor.description]

    
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

    def tuples(self, data=None):
        if not self.cursor:
            self.execute(data)
        while True:
            try:
                row = self.cursor.fetchone()
            except django.db.utils.ProgrammingError as dbe:
                self.dump()
                print(dbe)
            except psycopg2.ProgrammingError as pe:
                print(pe)
            if row is None:
                break
            yield row
        return

    def json(self, data=None, encoder=DjangoJSONEncoder):
        for d in self.dicts(data):
            yield json.dumps(d, cls=encoder)

    def objs(self, data=None):
        for d in self.dicts(data):
            yield DQResult(d, xquery=self)

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
        return "{}: {}".format(self.__class__.__name__, self.source)

    def __str__(self):
        l = []
        for i, d in enumerate(self.dicts()):
            l.append(d)
            if i == 10:
                break
        return str(l)

    def __iter__(self):
        return self.objs()

    def __enter__(self):

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if exc_type:
            pass
        else:
            pass
