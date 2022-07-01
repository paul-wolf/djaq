from typing import Union, List

import ipdb

def dump(node):
    if isinstance(node, B):
        return f"{dump(node.x)}, {node.conjunction}"
    elif isinstance(node, list):
        return ", ".join([dump(n) for n in node])
    elif isinstance(node, str):
       return node
        
class B:
    def __init__(self, n, conjunction="and"):
        """seq is a list."""
        self.x: Union[str, List] = n
        self.conjunction = conjunction

    def __str__(self):
        return stringify(self)

    def __repr__(self):
        return f"{self.__class__.__name__}: {stringify(self)}"


    def __and__(self, n: "B"):
        if isinstance(n, B):
            return B([self.x, n], conjunction="and")
        raise ValueError("Requires B() class")

    def __or__(self, n: "B"):
        # ipdb.set_trace()
        if isinstance(n, B):
            return B([self.x, n.x], conjunction="or")
        raise ValueError("Requires B() class")

def get_conjunction(n):
    if isinstance(n, B):
        return n.conjunction
    return None

def stringify(node, conjunction=None) -> str:
    """Produce a string representing the condition."""
    if isinstance(node, str):
        return node
    elif isinstance(node, B):
        if isinstance(node.x, str):
            return node.x
        elif isinstance(node.x, list):
            return stringify(node.x, node.conjunction)
    elif isinstance(node, list):
        s = ""
        for n in node:
            if s:
                 s += f" {conjunction} "
            conjunction_sub = conjunction
            if isinstance(n, list) and len(n) == 2:
                # because of the way we store conjoined B()s
                if isinstance(n[1], B):
                    conjunction_sub = n[1].conjunction
            s += f"{stringify(n, conjunction_sub)}"
        
        return f"({s})"

    raise Exception(f"Received unexpected type: {type(node)}")
