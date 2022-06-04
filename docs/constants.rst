Constants
---------

``None``, ``True``, ``False`` are replaced in SQL with ``NULL``,
``TRUE``, ``FALSE``. All of the following work:

::

   DQ("Book", "id, name").where("in_print is True")
   DQ("Book", "id, name").where("in_print is not True")
   DQ("Book", "id, name").where("in_print is False")
   DQ("Book", "id, name").where("in_print == True")