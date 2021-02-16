Constants
---------

``None``, ``True``, ``False`` are replaced in SQL with ``NULL``,
``TRUE``, ``FALSE``. All of the following work:

::

   DQ("(b.id, b.name) Book{in_print is True} b")
   DQ("(b.id, b.name) Book{in_print is not True} b")
   DQ("(b.id, b.name) Book{in_print is False} b")
   DQ("(b.id, b.name) Book{in_print == True} b")