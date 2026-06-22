import re


PLACEHOLDER_PATTERN = re.compile(r"\{([\w]*)\}")


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
        return any(value)
    # otherwise probably a string has context if not zero length or None
    return bool(value)


class ContextValidator(object):
    """Base class for validating context data.

    We assume context data is set before parsing.

    """

    def __init__(self, dq, context):
        self.data = context
        self.dq = dq

    def get(self, key, value):
        """Get the value for key.

        Override this method to clean,
        throw exceptions, cast, etc. for a specific value

        """
        return value

    def context(self):
        """Copy the context data.

        Override this to customise context data processing.

        """
        d = {}
        for k, v in self.data.items():
            # psycopg2 wants tuples or else it assumes ARRAY
            if isinstance(v, list):
                v = tuple(v)
            d[k] = self.get(k, v)
        return d
