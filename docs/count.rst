Count
-----

There are a couple ways to count results. These both return the exact
same thing:

.. code:: python

   DQ("Book").count()
   DQ("Book", "count(id)").value()
