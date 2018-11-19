import ast
from ast import AST, iter_fields, parse

from astpp import parseprint

# from app_utils import find_model_class, qualified_field, fieldclass_from_model

class Visitor(ast.NodeVisitor):

    code = ''
    
    stack = []

    def emit(self, s):
        self.code += str(s)
    
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
        self.emit(node.s)
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
        # print("ATTR: {}".format(node.attr))
        self.stack.append(node.attr)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Attribute):
                self.visit_Attribute(child)
            elif isinstance(child, ast.Name):
                self.stack.append(child.id)
            else:
                self.generic_visit(child)
        self.stack.reverse()
        if self.stack:
            self.code += "-".join(self.stack)
        self.stack = []
        


def parse_columns(s):
    """Parse column expressions."""

    tree = ast.parse(s)
    v = Visitor()
    v.visit(tree)

    print(v.code)

parse_columns("(avg(user.User.profile.organisation.logins, 2), u.created > '2018-01-01', (u.amount * 100)/2)")
