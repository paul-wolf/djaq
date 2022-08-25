import re

PLACEHOLDER_PATTERN = re.compile(r"\'\$\(([\w]*)\)\'")


class Node:
    def __init__(self, n, conjunction="and"):
        """seq is a list."""
        self.x = n  # can be str or List[Node]
        self.conjunction = conjunction

    def __str__(self):
        return render(self, {})

    def __repr__(self):
        return f"{self.__class__.__name__}: {render(self, {})}"

    def __and__(self, n):
        if isinstance(n, Node):
            return Node([self.x, n], conjunction="and")
        raise ValueError("Must Node class")

    def __or__(self, n):
        if isinstance(n, Node):
            return Node([self.x, n.x], conjunction="or")
        raise ValueError("Must be Node class")


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
        return any(
            value
        )  # otherwise probably a string is has context if not zero length or None
    return bool(value)


def render(node, ctx) -> str:

    if isinstance(node, str):
        return node if has_context(node, ctx) else ""
    elif isinstance(node, list):
        expressions = [render(n, ctx) for n in node]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = f" and ".join(expressions)
        return f"({s})"
    elif isinstance(node.x, str):
        return node.x if has_context(node.x, ctx) else ""
    elif isinstance(node.x, list):
        expressions = [render(n, ctx) for n in node.x]
        expressions = [e for e in expressions if e]
        if not expressions:
            return ""
        s = f" {node.conjunction} ".join(expressions)
        return f"({s})"
    raise Exception(f"Received unexpected type: {type(node)}")


if __name__ == "__main__":
    n = Node("b.pages > '$(pages)'") & Node("b.rating > '$(rating)'")

    # a = Node("b.id < 100")
    # b = Node("Publisher.id != '$(pppub_id)'")
    # c = Node("b.publish_date > today")
    # n = a & (b | c) | Node("b.price > 750")
    ctx = {"pages": 10}
    print(render(n, ctx))
