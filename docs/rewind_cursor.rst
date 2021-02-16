Rewind cursor
-------------

You can rewind the cursor but this is just executing the SQL again:

::

   list(dq.tuples())

   # now, calling `dq.tuples()` returns nothing

   list(dq.rewind().tuples())

   # you will again see results

If you call ``DjangoQuery.context(data)``, that will effectively rewind
the cursor since an entirely new query is created and the implementation
currently doesn’t care if ``data`` is the same context as previously
supplied.
