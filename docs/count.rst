Count
-----

There are a couple ways to count results. These both return the exact
same thing:

::

   DQ("(Book.id)").count()

   DQ("(count(Book.id)) Book").value()
