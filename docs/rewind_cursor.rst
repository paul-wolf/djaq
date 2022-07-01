Rewind cursor
-------------

You can rewind the cursor but this is just executing the SQL again:

.. code:: python

   list(dq.tuples())

   # now, calling `dq.tuples()` returns nothing

   list(dq.rewind().tuples())

   # you will again see results

If you call ``DjaqQuery.context(data)``, that will effectively rewind
the cursor since an the query is newly executed.