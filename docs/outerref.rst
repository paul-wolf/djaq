Django Subquery and OuterRef
----------------------------

The following do pretty much the same thing:

.. code:: python

   # QuerySet
   pubs = Publisher.objects.filter(pk=OuterRef('publisher')).only('pk')
   Book.objects.filter(publisher__in=Subquery(pubs))

   # Djaq
   DQ("Publisher", "id", name='pubs')
   DQ("Book", "name").where("publisher in '@pubs'")

Obviously, in both cases, you would be filtering Publisher to make it
actually useful, but the effect and verbosity can be extrapolated from
the above.

Most importantly, sending a query request over the wire, you can
reference the outer scope:

.. code:: python

   DQ("Book", '(name, ["(count(id)) Book{Publisher.id == b.publisher} b"]) Publisher p')

the subquery output expression references the outer scope. It evaluates
to the following SQL:

.. code:: sql

   SELECT
      "books_publisher"."name",
      (SELECT count("books_book"."id") FROM books_book WHERE "books_publisher"."id" = "books_book"."publisher_id")
   FROM books_publisher

There are some constraints on using subqueries like this. For instance,
the subquery cannot contain any joins.
