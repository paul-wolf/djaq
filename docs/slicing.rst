Offset, Limit, Paging, Slicing
==============================

You can use ``limit()`` and ``offset()`` to page your results:

.. code:: python

   DjangoQuery("...").offset(1000).limit(100).tuples()

Which will provide you with the first hundred results starting from the
1000th record.

You cannot slice a DjangoQuery because this would frustrate a design
goal of Djaq to provide the performance advantages of cursor-like
behaviour.

