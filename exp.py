import ast
from ast import AST, iter_fields, parse

from astpp import parseprint

# from app_utils import find_model_class, qualified_field, fieldclass_from_model

class Visitor(ast.NodeVisitor):
    def generic_visit(self, node):
        parseprint(node)
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Expr(self, node):
        parseprint(node)
        ast.NodeVisitor.generic_visit(self, node)
        print(")")
         
    def visit_Name(self, node):
        print("NAME: "+node.id)
        ast.NodeVisitor.generic_visit(self, node)
         
    def visit_Int(self, node):
        print(node.s)
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Num(self, node):
        print(node.s)
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Str(self, node):
        print(node.s)
        ast.NodeVisitor.generic_visit(self, node)
        
    def visit_Call(self, node):
        print("CALL: "+str(node.func))
        ast.NodeVisitor.generic_visit(self, node)
        
    stack = []
    def visit_Attribute(self, node):
        print("ATTR: {}".format(node.attr))
        self.stack.append(node.attr)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Attribute):
                self.visit_Attribute(child)
        self.stack.reverse()                
        print("***********: "+".".join(self.stack))
        self.stack = []
        


def parse_columns(s):
    """Parse column expressions."""

    tree = ast.parse(s)
    v = Visitor()
    v.visit(tree)

parse_columns("(avg(user.User.profile.organisation.logins), u.created > '2018-01-01')")
