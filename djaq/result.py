"""Result class
Thanks to http://code.activestate.com/recipes/577887-a-simple-namespace-class/
"""
from collections.abc import Mapping, Sequence


class _Dummy:
    ...


CLASS_ATTRS = dir(_Dummy)
del _Dummy


class DQResult(dict):
    """
    A class providing a namespace to DjangoQuery result attributes.

    """

    def __init__(self, obj, dq):
        super().__init__(obj)
        self.dq = dq

    def __dir__(self):
        return tuple(self)

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__, super().__repr__())

    def __getattribute__(self, name):
        try:
            return self[name]
        except KeyError:
            # search related attributes
            msg = "'%s' object has no attribute '%s'"
            raise AttributeError(msg % (type(self).__name__, name))

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]

    def cursor_descriptor(self):
        return self.dq.cursor.description

    # ------------------------
    # "copy constructors"

    @classmethod
    def from_object(cls, obj, names=None):
        if names is None:
            names = dir(obj)
        ns = {name: getattr(obj, name) for name in names}
        return cls(ns)

    @classmethod
    def from_mapping(cls, ns, names=None):
        if names:
            ns = {name: ns[name] for name in names}
        return cls(ns)

    @classmethod
    def from_sequence(cls, seq, names=None):
        if names:
            seq = {name: val for name, val in seq if name in names}
        return cls(seq)

    # ------------------------
    # static methods

    @staticmethod
    def hasattr(ns, name):
        try:
            object.__getattribute__(ns, name)
        except AttributeError:
            return False
        return True

    @staticmethod
    def getattr(ns, name):
        return object.__getattribute__(ns, name)

    @staticmethod
    def setattr(ns, name, value):
        return object.__setattr__(ns, name, value)

    @staticmethod
    def delattr(ns, name):
        return object.__delattr__(ns, name)


def as_namespace(obj, names=None):

    # functions
    if isinstance(obj, type(as_namespace)):
        obj = obj()

    # special cases
    if isinstance(obj, type):
        names = (name for name in dir(obj) if name not in CLASS_ATTRS)
        return DQResult.from_object(obj, names)
    if isinstance(obj, Mapping):
        return DQResult.from_mapping(obj, names)
    if isinstance(obj, Sequence):
        return DQResult.from_sequence(obj, names)

    # default
    return DQResult.from_object(obj, names)
