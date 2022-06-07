Subqueries and ``in`` Clause
============================

You can reference subqueries within a Djaq query.

.. code:: python

   v_sub = DQ(Book, "id", name="v_sub").where("name == 'B*'")  # noqa: F841
   DQ(Book, "name, price").where("id in '@v_sub'").go()

This evaluates to: 

::

   SELECT "books_book"."name", "books_book"."price" 
      FROM books_book WHERE "books_book"."id" 
      IN (SELECT "books_book"."id" FROM books_book WHERE "books_book"."name" LIKE \'B%\')

Note that user of single quotes and prepending the sub query name with ``@``:  ``'@queryname'``

Make sure your subquery returns a single output column.

.. code:: python

   DQ("Book", "id").where("name == 'B*'", name='dq_sub')
   dq = DQ("Book", "name, price").where("id in '@dq_sub'")

As with QuerySets it is nearly always faster to generate a sub query
than use an itemised list.

If your subquery has parameters, these need to be supplied to the using query:

.. code:: python

   DQ("Book", "id", name="dq_sub").where("ilike(name, {spec})")
   DQ("Book", "name, price").where("id in '@dq_sub'").context({"spec": "B%"})

