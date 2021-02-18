class B:
    def __init__(self, n, conjunction="and"):
        """seq is a list."""
        self.x = n  # can be str or List[B]
        self.conjunction = conjunction

    def __str__(self):
        return stringify(self)

    def __repr__(self):
        return f"{self.__class__.__name__}: {stringify(self)}"

    def __and__(self, n):
        if isinstance(n, B):
            return B([self.x, n], conjunction="and")
        raise ValueError("Must B() class")

    def __or__(self, n):
        if isinstance(n, B):
            return B([self.x, n.x], conjunction="or")
        raise ValueError("Must be B() class")


def stringify(node) -> str:
    if isinstance(node, str):
        return node
    elif isinstance(node, list):
        s = f" and ".join([stringify(n) for n in node])
        return f"({s})"
    elif isinstance(node.x, str):
        return node.x
    elif isinstance(node.x, list):
        s = f" {node.conjunction} ".join([stringify(n) for n in node.x])
        return f"({s})"
    raise Exception(f"Received unexpected type: {type(node)}")