import ast
from ast import AST, iter_fields, parse

from astpp import parseprint

from app_utils import find_model_class, qualified_field, fieldclass_from_model

class XQueryVisitor(ast.NodeVisitor):

    def make_relations(self, attribute_list):
        while attribute_list:
            attribute_list.pop()
    
    class Relation(object):
        
        def __init__(self, f, related_table, related_field):
            self.field = f
            self.related_table = related_table
            self.related_field = related_field
            self.join_type = 'left'
            
        def key(self):
            return "{}.{}".format(self.related_table, self.related_field)
        
    relations = []
    code = ''    
    stack = []

    def emit(self, s):
        self.code += str(s)
    
    def emit_single_quoted(self, s):
        self.code += "'{}'".format(s)
    
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
        self.emit_single_quoted(node.s)
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Call(self, node):
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
                self.generic_visit(child)
        self.stack.reverse()
        emit(make_relations(self.stack))
        # if self.stack:
        #    self.code += "-".join(self.stack)
        self.stack = []


def parse_columns(s):
    """Parse column expressions."""

    tree = ast.parse(s)
    v = XQueryVisitor()
    v.visit(tree)

    print(v.code)

parse_columns("Book.name, Book.publisher.name, count(User.name)")
