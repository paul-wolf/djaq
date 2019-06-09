#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
astpp
=====
A pretty-printing dump function for the ast module.  The code was copied from
the ast.dump function and modified slightly to pretty-print.

Alex Leone (acleone ~AT~ gmail.com), 2010-01-30

Usage
-----

ipython
~~~~~~~

Add the following in your ipython profile config:

.. code:: python

    c = get_config()

    try:
        import astpp
    except ImportError:
        pass
    else:
        c.TerminalIPythonApp.extensions.append('astpp')
        c.InteractiveShellApp.extensions.append('astpp')
"""
from __future__ import print_function

from ast import AST, iter_fields, parse


def dump(node, annotate_fields=True, include_attributes=False, indent="  "):
    """
    Return a formatted dump of the tree in *node*.  This is mainly useful for
    debugging purposes.  The returned string will show the names and the values
    for fields.  This makes the code impossible to evaluate, so if evaluation is
    wanted *annotate_fields* must be set to False.  Attributes such as line
    numbers and column offsets are not dumped by default.  If this is wanted,
    *include_attributes* can be set to True.
    """

    def _format(node, level=0):
        if isinstance(node, AST):
            fields = [(a, _format(b, level)) for a, b in iter_fields(node)]
            rv = "%s(%s" % (
                node.__class__.__name__,
                ", ".join(
                    ("%s=%s" % field for field in fields)
                    if annotate_fields
                    else (b for a, b in fields)
                ),
            )
            if include_attributes and node._attributes:
                rv += fields and ", " or " "
                rv += ", ".join(
                    "%s=%s" % (a, _format(getattr(node, a))) for a in node._attributes
                )
            return rv + ")"
        elif isinstance(node, list):
            lines = ["["]
            lines.extend(
                (indent * (level + 2) + _format(x, level + 2) + "," for x in node)
            )
            if len(lines) > 1:
                lines.append(indent * (level + 1) + "]")
            else:
                lines[-1] += "]"
            return "\n".join(lines)
        return repr(node)

    if not isinstance(node, AST):
        raise TypeError("expected AST, got %r" % node.__class__.__name__)
    return _format(node)


def parseprint(source, filename="<unknown>", mode="exec", **kwargs):
    """Parse the source and pretty-print the AST."""
    node = parse(source, filename, mode=mode)
    print(dump(node, **kwargs))


# Short name: pdp = parse, dump, print
pdp = parseprint


def load_ipython_extension(ip):
    from IPython.core.magic import Magics, magics_class, line_cell_magic

    @magics_class
    class AstMagics(Magics):
        @line_cell_magic
        def astpp(self, line="", cell=None):
            """Parse the a python code or expression and pretty-print the AST.

            Usage, in line mode:
              %astpp statement
            or in cell mode:
              %%astpp
              code
              code...

            Examples
            --------
            ::
            In [1]: %astpp pass
            Module(body=[
                Pass(),
              ])

            In [2]: %astpp from ..main.app import foo as bar
            Module(body=[
                ImportFrom(module='main.app', names=[
                    alias(name='foo', asname='bar'),
                  ], level=2),
              ])
            """
            opts, stmt = self.parse_options(line, "", posix=False, strict=False)
            if stmt == "" and cell is None:
                return
            transform = self.shell.input_splitter.transform_cell
            if cell is None:  # called as line magic
                ast_stmt = self.shell.compile.ast_parse(transform(stmt))
            else:
                ast_stmt = self.shell.compile.ast_parse(transform(cell))
            self.shell.user_ns["_"] = ast_stmt
            print(dump(ast_stmt))

    ip.register_magics(AstMagics)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "infile", nargs="?", type=argparse.FileType("r"), default=sys.stdin
    )
    args = parser.parse_args()
    parseprint(args.infile.read(), filename=args.infile.name, include_attributes=True)
