Subqueries and ``in`` Clause
============================

You can reference subqueries within a Djaq expression using

-  Another DjangoQuery
-  A Queryset
-  A list

The two most useful cases are using a subquery in the filter condition:

.. code:: python

   DQ('(b.id, b.name) Book{b.id in ["(Book.id)"]} b')

And using a subquery in the selected columns expression:

.. code:: python

   DQ('(p.name, ["(count(b.id)) Book{Publisher.id == b.publisher} b"]) Publisher p')

You can use an IN clause with the keyword ``in`` (note lower case) If
you are writing queries via the Python API. Create one DjangoQuery and
reference it with ``@queryname``:

.. code:: python

   DQ("(b.id) Book{name == 'B*'} b", name='dq_sub')
   dq = DQ("(b.name, b.price) Book{id in '@dq_sub'} b")

Note that you have to pass a name to the DjangoQuery to reference it
later. We can also use the ``data`` parameter to pass a QuerySet to the
DjangoQuery:

.. code:: python

   qs = Book.objects.filter(name__startswith="B").only('id')
   dq = DQ("(b.name, b.price) Book{id in '@qs_sub'} b", names={"qs_sub": qs})

   qs = Book.objects.filter(name__startswith="B").only('id')
   ids = [rec.id for rec in qs]
   dq = DQ("(b.name, b.price) Book{id in '@qs_sub'} b", names={"qs_sub": ids})

As with QuerySets it is nearly always faster to generate a sub query
than use an itemised list.
