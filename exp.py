import csv
import io
import json
import re
import ast
from ast import AST, iter_fields, parse
from collections import defaultdict

from django.db import connections, models
from django.db.models.query import QuerySet
from django.db.models.sql import UpdateQuery
from django.utils.text import slugify
from . instance import XQueryInstance

def _get_db_type(field, connection):
    if isinstance(field, (models.PositiveSmallIntegerField,
                          models.PositiveIntegerField)):
        # integer CHECK ("points" >= 0)'
        return field.db_type(connection).split(' ', 1)[0]

    return field.db_type(connection)

from . astpp import parseprint

from . app_utils import model_field, find_model_class


def model_path(model):
    return "{}.{}".format(model.__module__,
                          model._meta.object_name)



class XQuery(ast.NodeVisitor):

    # keep a record of named instances
    directory = {}
    
    aggregate_functions = {
        "unknown": ['avg', 'count', 'max', 'min', 'sum', ],        
        "sqlite": ['avg', 'count', 'group_concat', 'max', 'min', 'sum', 'total', ],
        "postgresql": ['avg', 'count', 'max', 'min', 'sum', 'stddev', 'variance', ],
    }
    
    class JoinRelation(object):
        JOIN_TYPES = {
            "->": "LEFT JOIN",
            "<-": "RIGHT JOIN",
            "<>": "INNER JOIN", 
        }
        def __init__(self, model, xquery, fk_relation=None, fk_field=None, related_field=None,
                     join_type='->', alias=None):
            self.model = model
            self.fk_relation = fk_relation
            self.fk_field = fk_field
            self.related_field = related_field
            self.join_type = join_type # left, right, inner
            self.alias = alias
            self.select = ''
            self.expression_str = ''
            self.column_expressions = []
            self.where = ''
            self.group_by = False
            self.xquery = xquery
            
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
                return XQuery.JoinRelation.JOIN_TYPES[self.join_type]
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
                s += '{}.{} = {}.{}'.format(fk.model._meta.db_table,
                                            fk.column,
                                            f.model._meta.db_table,
                                            f.column)
            return "({})".format(s)
        
        def group_by_columns(self):
            """Return str of GROUP BY columns."""
            grouping = []
            print("group by columns: {}".format(self.column_expressions))
            for c in self.column_expressions:
                if not self.xquery.is_aggregate_expression(c):
                    grouping.append(c)
            print("*"*77)
            print("grouping: ".format(grouping))
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

    
    def __init__(self, source, using='default', limit=None, name=None):

        if name:
            XQuery.directory[name]  = self
        
        self.connection = connections[using]
        self.vendor = self.connection.vendor
        # self.compiler = query.get_compiler(connection=connection)

        self.relation_index = 0  # this is the relation being parsed currently
        self.source = source
        self.limit = limit
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
        self.expression_context = 'select' # change to 'where' later
        # self.group_by = False
        if self.vendor in XQuery.aggregate_functions:
            self.vendor_aggregate_functions = XQuery.aggregate_functions[self.vendor]
        else:
            self.vendor_aggregate_functions = XQuery.aggregate_functions['unknown']
        self.column_headers = []

    def aggregate(self):
        """Indicate that the current relation requires aggregation."""
        # print("Setting group by: {}".format(self.relations[self.relation_index]))
        self.relations[self.relation_index].group_by = True

    def add_relation(self, model,
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
                        # these means we have two different aliases
                        # let a new relation be created
                        pass
                else:
                    if alias:
                        relation.alias = alias
                    return relation

        relation = XQuery.JoinRelation(model, self,
                                       fk_relation,
                                       fk_field,
                                       related_field,
                                       join_type,
                                       alias)
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

    def emit_select(self, s):
        self.relations[self.relation_index].select += str(s)
        self.relations[self.relation_index].expression_str += str(s)        
    
    def push_column_expression(self, s):
        self.relations[self.relation_index].column_expressions.append(s)
    
    def emit_where(self, s):
        self.relations[self.relation_index].where += str(s)

    def emit(self, s):
        if self.expression_context == 'select':
            self.emit_select(s)
        elif self.expression_context == 'where':
            self.emit_where(s)
    
    def single_quoted(self, s):
        return "'{}'".format(s)
    
    def generic_visit(self, node):
        if not isinstance(node, ast.Load):
            # parseprint(node)
            pass
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Expr(self, node):
        
        # parseprint(node)
        ast.NodeVisitor.generic_visit(self, node)

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

        
        if "*" in node.s:
            if self.relations[self.relation_index].where.endswith(' = '):
                s = s.replace("*", "%")                
                parts = self.relations[self.relation_index].where.rpartition(' = ')
                self.relations[self.relation_index].where = parts[0] + ' LIKE '
        
        # if node.s preceded by equals
        # replace equals with LIKE (or ilike)
        # and replace start with %
        self.emit(self.single_quoted(s))
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Call(self, node):
        if node.func.id.lower() in XQuery.aggregate_functions[self.vendor]:
            self.aggregate()
        self.emit(node.func.id + "(")
        for i, arg in enumerate(node.args):
            if i:
                self.emit(", ")
            ast.NodeVisitor.visit(self, arg)
        self.emit(")")

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
        print("v"*44)
        print("equals")
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
        print("v"*44)
        print(node.op)
        print("^"*44)        
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

    def visit_Tuple(self, node):
        for i, el in enumerate(node.elts):
            print("v"*66)
            parseprint(el)

            ast.NodeVisitor.visit(self, el)
            exp = self.relations[self.relation_index].expression_str
            
            self.push_column_expression(exp.strip(', '))
            self.relations[self.relation_index].expression_str = ''
            print("^"*66)
            if not i == len(node.elts)-1:
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
                relation_sources.append(s[:search.start()+offset].strip())
                # print("FOUND: {}, start={}".format(s[:search.start()+offset], search.start()))
                s = s[search.start()+offset:]
                # print("REDUCED: {}".format(s))
            else:
                relation_sources.append(s.strip())
                # print("LAST: {}".format(s))
                break
            
            offset = 2
            # input("Press Enter to continue...")

        return relation_sources

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
        print("parse column aliases: {}".format(s))
        m = True
        for col in self.get_col(s):
            a = col.split(" as ")
            if len(a) == 1:
                aliases.append((a[0], slugify(a[0].replace(".", "_").replace(" ", "_")).replace("-", "_")))
            elif len(a) == 2:
                aliases.append((a[0], a[1]))
            else:
                raise Exception("Error defining column")
            
        return aliases

            
    def parse(self):
        """Parse column expressions.

        If you call it twice, it fails second time.

        """
        
        if self.sql:
            return self.sql

        pattern = "(->|<-|<>)?\s*(\(.*\))?\s*([\w]+)[\s]*(\{.*\})?\s*([\w]+)?"
        
        """
        We get a relation string like this: 
        
        ->(Book.name as title, Book.publisher.name as pub, count()) Book{length(b.name) > 50)} b  

        group 1: join operator
        group 2: column expressions
        group 3: model
        group 4: filter
        group 5: alias
        """
        relation_sources = self.split_relations(self.source)
        print("relation_sources: {}".format(relation_sources))

        for i, relation_source in enumerate(relation_sources):
            print("Parsing relation: {}".format(relation_source))
            
            m = re.match(pattern, relation_source)
            if m:
                join_type = m.group(1)
                select_src = m.group(2)
                model_name = m.group(3)
                where_src = m.group(4)
                alias = m.group(5) if m.group(5) else model_name
            elif re.match("^(\(.*\))$", self.source):
                join_type = None
                # strip whitespace
                src = self.source.strip()
                if src[0] == "(":
                    src = src[1:-1]
                select_src = src.strip()
                model_name = None
                where_src = None
                alias = None
            else:
                raise Exception("Invalid source")

            print("join_type={}, select_src={}, model_name={}, where_src={}, alias={}".format(
                join_type,
                select_src,
                model_name,
                where_src,
                alias))

            # we need to generate column headers and remove
            # aliases. tuples are (exp, alias)
            column_tuples = self.parse_column_aliases(select_src)
            self.column_headers = [c[1] for c in column_tuples]
            select_src = ", ".join([c[0] for c in column_tuples])
            relation = self.find_relation_from_alias(alias)
            model = find_model_class(model_name)
            if model and not relation:
                relation = self.add_relation(model=model, alias=alias)
                print("Created JoinRelation: {}".format(relation))
            else:
                print("Relation already existed: {}".format(relation))

            self.relation_index = i

            if select_src:
                self.expression_context = 'select'
                self.visit(ast.parse(select_src))
                
            if where_src:
                self.expression_context = 'where'
                self.visit(ast.parse(where_src))

        # print("Database vendor: {}".format(self.vendor))

        for r in self.relations:
            print("Relation        : {}".format(str(r)))
            print("   join         : {}".format(r.join_type))
            print("   fk_relation  : {}".format(r.fk_relation))
            print("   fk_field     : {}".format(r.fk_field))
            print("   related_field: {}".format(r.related_field))            
            print("   select       : {}".format(r.select))            
            print("   where        : {}".format(r.where))
            print("   alias        : {}".format(r.alias))

        self.relations.reverse()

        master_relation = self.relations.pop()
        s = "SELECT {} FROM {}".format(master_relation.select, master_relation.model_table)
        for i, relation in enumerate(self.relations):
            s += " {} {} ON {} ".format(relation.join_operator, relation.model_table, relation.join_condition_expression)
            if relation.where:
                s += " WHERE {}".format(relation.where)
        if master_relation.where:
            s += " WHERE {}".format(master_relation.where)
        if master_relation.group_by:
            gb = master_relation.group_by_columns()
            if gb:
                s += " GROUP BY {}".format(gb)
        if self.limit:
            s += " LIMIT {}".format(int(self.limit))
        self.sql = s
        return self.sql
    
    def execute(self, parameters=None):
        sql = self.parse()
        print(sql)
        sql = sql.replace("'%s'", "%s")
        self.cursor = self.connection.cursor().execute(sql, parameters)
        # we record the column names from the cursor
        # but we have our own aliases in self.column_headers
        self.col_names = [desc[0] for desc in self.cursor.description]
        
    def dicts(self, parameters=None):
        if not self.cursor:
            self.execute(parameters)
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            row_dict = dict(zip(self.column_headers, row))
            yield row_dict
        return
    
    def tuples(self, parameters=None):
        if not self.cursor:
            self.execute(parameters)
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            yield row
        return

    def json(self, parameters=None):
        for d in self.dicts(parameters):
            yield json.dumps(d)

    def objs(self, parameters=None):
        for d in self.dicts(parameters):
            yield XQueryInstance(d, xquery=self)
            

    def csv(self, parameters=None):
        if not self.cursor:
            self.execute(parameters)
        while True:
            output = io.StringIO()
            row = self.cursor.fetchone()
            if row is None:
                break
            writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
            writer.writerow(row)
            yield output.getvalue()
        
