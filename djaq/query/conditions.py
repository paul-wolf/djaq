from .context import has_context


def render_conditions_drop_empty(node, ctx) -> str:
    """Produce a string repesenting all expressions
    in the node tree as a single expression.
    If a B() node expression references a parameter,
    {somevariable}, we check if the context can supply that variable.
    if not we drop that node from the final expression.
    """
    if isinstance(node, str):
        return node if has_context(node, ctx) else ""
    elif isinstance(node, list):
        expressions = [render_conditions_drop_empty(n, ctx) for n in node]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = " and ".join(expressions)
        return f"({s})"
    elif isinstance(node.x, str):
        return node.x if has_context(node.x, ctx) else ""
    elif isinstance(node.x, list):
        expressions = [render_conditions_drop_empty(n, ctx) for n in node.x]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = f" {node.conjunction} ".join(expressions)
        return f"({s})"
    raise Exception(f"Received unexpected type: {type(node)}")


def render_conditions(node, ctx) -> str:
    """Produce a string repesenting all expressions
    in the node tree as a single expression.
    """
    if isinstance(node, str):
        return node
    elif isinstance(node, list):
        expressions = [render_conditions(n, ctx) for n in node]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = " and ".join(expressions)
        return f"({s})"
    elif isinstance(node.x, str):
        return node.x
    elif isinstance(node.x, list):
        expressions = [render_conditions(n, ctx) for n in node.x]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = f" {node.conjunction} ".join(expressions)
        return f"({s})"
    raise Exception(f"Received unexpected type: {type(node)}")
