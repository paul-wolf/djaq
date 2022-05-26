Subqueries and ``in`` Clause
============================

You can reference subqueries within a Djaq expression using

-  Another DjangoQuery
-  A Queryset
-  A list

The two most useful cases are using a subquery in the filter condition:

.. code:: python

   DQ("Book", "id, name").where("id in ['(id)']")

And using a subquery in the selected columns expression:

.. code:: python

   DQ("Book", "publisher.name, ["(count(b.id)) Book{Publisher.id == b.publisher} b"]) Publisher p')

You can use an IN clause with the keyword ``in`` (note lower case) If
you are writing queries via the Python API. Create one DjangoQuery and
reference it with ``@queryname``:

.. code:: python

   DQ("Book", "id").where("name == 'B*'", name='dq_sub')
   dq = DQ("Book", "name, price").where("id in '@dq_sub'")

Note that you have to pass a name to the DjangoQuery to reference it
later. We can also use the ``data`` parameter to pass a QuerySet to the
DjangoQuery:

.. code:: python

   qs = Book.objects.filter(name__startswith="B").only('id')
   dq = DQ("Book", "name, price").where("id in '@qs_sub'", names={"qs_sub": qs})

   qs = Book.objects.filter(name__startswith="B").only('id')
   ids = [rec.id for rec in qs]
   dq = DQ("Book", "name, b.price").where("id in '@qs_sub'", names={"qs_sub": ids})

As with QuerySets it is nearly always faster to generate a sub query
than use an itemised list.
