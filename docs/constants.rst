TRUE, FALSE, NULL, Empty
------------------------

``None``, ``True``, ``False`` are replaced in SQL with ``NULL``,
``TRUE``, ``FALSE``. All of the following work:

.. code:: python

   DQ("Book", "id, name").where("in_print is True")
   DQ("Book", "id, name").where("in_print is not True")
   DQ("Book", "id, name").where("in_print is False")
   DQ("Book", "id, name").where("in_print == True")

To test for ``NULL``, use ``None``:

.. code:: python

   DQ("Book", "id, name").where("name is not None")
   
If you want to test for an empty or non-empty string, use ``LENGTH()``:

.. code:: python

   DQ("Book", "id, name").where("length(name) > 0")


