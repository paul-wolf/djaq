from tokenize import tokenize, generate_tokens, untokenize, NUMBER, STRING, NAME, OP, EXACT_TOKEN_TYPES
from token import *
from io import BytesIO

"""
Node
NodeSelectExpression
NodeAliasedSelection
NodeLeftJoin
NodeRightJoin
NodeOutterJoin
"""

# constant: int, float, string, etc.
# term: identifer | constant | function_call | parentheti

# binary expression: expression OP expression
# unary expression: OP expression
# expression_group: (expression)
# expression_sequence: expression, ...
# function_call: identifier(expression_sequence)
# column_expression: expression as alias
# column_list := [column_expression, ...]
# filter : {boolean_expression}
# query: ModelName filter  | `SQL select` | XQuery | QuerySet
# aliased_query := select_expression alias  
# select: column_list aliased_selection column_list
# left_join := aliased_selection -> aliased_selection
# right_join := aliased_selection <- aliased_selection
# inner_join := aliased_selection <-> aliased_selection
# join := left_join | right_join | inner_join

# identifier: [\w]+
# accessor_property: identifier.identifer | constant.identifier
# function: identifier(expression_sequence)
# accessor_function: identifier.function
# binary operation: expression op expression
# unary operation: op expression

# model expression
# User u
# User {} u

# with column_expressions
# (column_expression_list): User {} u
# User {} u []


class Node(object):
    pass

class NodeSelect(Node):

    def __init__(column_expressions_node, select_expression):
        self.column_expression_node = column_expression_node
        self.select_expression = select_expression

class NodeColumnExpressions(Node):
    def __init__(column_expression_list):
        self.column_expressions = column_expression_list
        


# our parse tree
body = []


def look_ahead(token_list, position, skip_ws=True):
    while True:
        token_info = token_list[position]
        if not (token_info.type == COMMENT or token_info.type == NL):
            return token_info
        
def get_next_token(token_list, position, skip_ws=True):
    """Get next token: skipping whitespace and commas"""

    while True:
        token_tuple = token_tuple[position]

    return token, token_type, position

def get_expression_node(token_list, position):
    """Get an expression.

    Until we hit a comma that is not part of a function param list.

    Example expressions:
    x.oc as org_code
    o.name
    count(*)
    'i am a literal'
    x.price * (.04 * x.price_factor)

    """
    


def get_column_expressions(token_list, position):
    """Start with l bracket until closing bracket.
    Return a list of column_expressions
    column_expression := expression as alias

    [x.oc as org_code, o.name, count(*), 'i am a literal']
    
    """

    column_nodes = []
    i = position
    while True:
        col_expression_node, i = get_next_column_expression_node(token_list, i)
        if col_expression_node:
            column_expressions.append(column_expression_node)
        else:
            break
    return column_nodes, i


def get_select(token_list, position):
    pass



def tokenize_dql(s):
    """
    """
    result = []
    g = tokenize(BytesIO(s.encode('utf-8')).readline)
    for i in g:
        result.append(i)
    return result



s = """
(u.username, 
        u.email, 
        x.oc): 
       User {(username.startswith('paul') | username == 'chris') & email == '@bitposter.co'} u 
        -> extendeduser x
"""

s1 = """
 
User {(username.startswith('paul') or username == i'chris') and email .= '@bitposter.co'} 
    -> ExtendedUser x
    -> Organisation{ e.dt_create >= `CURRENT_DATE - interval '7 day'` } o:u.oc==o.id
    -> SELECT * from sometable where id in `[i for i in some_itable]` x

group_by x.oc, o.name  # make this implicit 

[x.oc as org_code, o.name, count(*), 'i am a literal', x.price * 2]

"""
s = "{username.startswith('paul') or (username == 'chris' AND email ~ '@bitposter.co')}"
s = """[x.oc as org_code, 
        o.name, count(*), # try to count
      'i am a literal', x.price * 2]
"""

tokens = tokenize_dql(s)
for token_info in tokens:
     print(tok_name[token_info.type].ljust(12), token_info.string)

import ast

# https://python-ast-explorer.com/



# https://github.com/DimaKudosh/django-prepared-query/blob/master/django_prepared_query/compiler.py
