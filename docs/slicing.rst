Offset, Limit, Paging, Slicing
==============================

You can use ``limit()`` and ``offset()`` to page your results:

.. code:: python

   DjaqQuery("...").offset(1000).limit(100).tuples()

Which will provide you with the first hundred results starting from the
1000th record.

You cannot slice a DjaqQuery because this would frustrate a design
goal of Djaq to provide the performance advantages of cursor-like
behaviour.

But you can slice the result of the QuerySet method:

.. code:: python

   DQ("Book").qs()[10:20]