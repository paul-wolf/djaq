import re
import ast
from ast import AST, iter_fields, parse
from collections import defaultdict

from django.db import connections, models
from django.db.models.query import QuerySet
from django.db.models.sql import UpdateQuery

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
        def __init__(self, model, fk_relation=None, fk_field=None, related_field=None,
                     join_type='left', alias=None):
            self.model = model
            self.fk_relation = fk_relation
            self.fk_field = fk_field
            self.related_field = related_field
            self.join_type = join_type # left, right, inner
            self.alias = alias
            self.select = ''
            self.where = ''
            
        @property
        def model_table(self):
            return self.model._meta.db_table
        
        def field_reference(self, field_model):
            return "{}.{}".format(self.related_table, self.related_field)

        def is_model(self, model):
            return model_path(model) == model_path(self.model)

        @property
        def join_operator(self):
            if join_type:
                return JoinRelation.JOIN_TYPES[self.join_type]
            return 'LEFT JOIN'
        
        def __str__(self):
            return "{}".format(model_path(self.model))
        
    def find_relation(self, alias):
        for relation in self.relations:
            if alias == relation.alias:
                return relation
            
    def __init__(self, source, using='default'):
        
        self.connection = connections[using]
        self.vendor = self.connection.vendor
        # self.compiler = query.get_compiler(connection=connection)

        self.relation_index = 0  # this is the relation being parsed currently
        self.source = source
        self.sql = None
        self.cursor = None
        self.col_names = None
        self.relations = []
        self.code = ''    
        self.stack = []
        self.names = []
        self.relations = []
        self.group_by = False
        self.parsed = False
        self.expression_context = 'select' # change to 'where' later
        self.group_by = False
        if self.vendor in XQuery.aggregate_functions:
            self.vendor_aggregate_functions = XQuery.aggregate_functions[self.vendor]
        else:
            self.vendor_aggregate_functions = XQuery.aggregate_functions['unknown']


    def aggregate(self):
        """Indicate that the current relation requires aggregation."""
        self.relations[self.relation_index].group_by = True
        
    def push_relations(self, attribute_list):
        
        f = None
        r = None # relation of field f
        
        # get field to represent in select expression
        f = attribute_list.pop()
        # get the model or FK relation it belongs to
        if len(attribute_list):
            r = attribute_list.pop()
        else:
            # it was alone; find default model
            pass
        model, field = model_field(r, f)
        # don't join to model we already have
        for relation in self.relations:
            if relation.is_model(model):
                break
        else:
            # not found, so add it
            self.relations.append(XQuery.JoinRelation(model = model))
            
        return "{}.{}".format(model._meta.db_table, field.column)
    
    def emit_select(self, s):
        self.relations[self.relation_index].select += str(s)
    
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
        ast.NodeVisitor.generic_visit(self, node)
         
    def visit_Int(self, node):
        self.emit(node.n)
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Num(self, node):
        self.emit(node.n)
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Str(self, node):
        self.emit(self.single_quoted(node.s))
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

    def visit_Gt(self, node):
        self.emit(" > ")
        ast.NodeVisitor.generic_visit(self, node)

    def visit_Lt(self, node):
        self.emit(" < ")
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Eq(self, node):
        self.emit(" == ")
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

    def visit_Tuple(self, node):
        for i, el in enumerate(node.elts):
            parseprint(el)
            ast.NodeVisitor.visit(self, el)
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

        self.stack.reverse()
        column_expression = self.push_relations(self.stack)
        self.names.append(column_expression)
        self.emit(column_expression)
        if self.stack:
            self.code += "-".join(self.stack)

        self.stack = []

    def split_relations(self, s):
        """Split string by join operators returning a list."""

        relation_sources = []
        search = None
        offset = 0        
        while True:
            print("SEARCHING: {}, offset={}".format(s, offset))
            search = re.search("->|<-|<>", s[offset:])

            if search:
                relation_sources.append(s[:search.start()+offset].strip())
                print("FOUND: {}, start={}".format(s[:search.start()+offset], search.start()))
                s = s[search.start()+offset:]
                print("REDUCED: {}".format(s))
            else:
                relation_sources.append(s.strip())
                print("LAST: {}".format(s))
                break
            
            offset = 2
            # input("Press Enter to continue...")

        return relation_sources
    
    def parse(self):
        """Parse column expressions.

        If you call it twice, it fails second time.

        """
        
        if self.sql:
            return self.sql

        
        
        pattern = "(->|<-|<>)?\s*(\(.*\))?\s*([\w]+)[\s]*(\{.*\})?\s+([\w]+)?"
        
        """
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
            print(relation_source)
            
            m = re.match(pattern, relation_source)
            join_type = m.group(1)
            select_src = m.group(2)
            model_name = m.group(3)
            where_src = m.group(4)
            alias = m.group(5) if m.group(5) else model_name

            relation = self.find_relation(alias)
            model = find_model_class(model_name)
            if not relation:
                relation = XQuery.JoinRelation(model=model, alias=alias)
                
            self.relation_index = i

            if select_src:
                self.expression_context = 'select'
                self.visit(ast.parse(select_src))

            if where_src:
                self.expression_context = 'where'
                self.visit(ast.parse(where_src))
        
        # print("Database vendor: {}".format(self.vendor))
        
        for r in self.relations:
            print("Relation: {}".format(str(r)))

        self.relations.reverse()

        master_relation = self.relations.pop()
        s = "SELECT {} FROM {}".format(master_relation.select, master_relation.model_table)
        for i, relation in enumerate(self.relations):
            if relation.select: # means it's a subquery
                s += "{} (SELECT {} FROM {} ".format(relation.join_operator, relation.select, relation.model_table)
                if relation.where:
                    s += "WHERE {}".format(relation.where)
        # if self.group_by:
        #    s += " GROUP BY {}".format(", ".join(set(self.names)))
        self.sql = s
        return self.sql
    
    def execute(self):
        sql = self.parse()
        parameters = defaultdict(list)
        self.cursor = self.connection.cursor().execute(sql, parameters)
        self.col_names = [desc[0] for desc in self.cursor.description]
        
    def dicts(self):
        if not self.cursor:
            self.execute()
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            row_dict = dict(zip(self.col_names, row))
            yield row_dict
        return
    
    def tuples(self):
        if not self.cursor:
            self.execute()
        while True:
            row = self.cursor.fetchone()
            if row is None:
                break
            yield row
        return
