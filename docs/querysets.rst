Comparing to Django QuerySets
-----------------------------

Djaq is not a replacement for Querysets. They have different purposes.
The QuerySet API is not a remote API. You can use Djaq queries inside
your Django application and Djaq syntax can be more intuitive and
simpler than QuerySets. But Querysets are highly integrated with Django
and have been developed over 15 years by many developers. Plus you get
code completion in your IDE with QuerySets. It is a very well thought
out framework that is the best choice working within a service based on
Django’s ORM. You could probably write a complete transactional Django
application with Djaq and not use QuerySets at all but you’d be going
against the framework.

This section is intended to highlight differences for users with high
familiarity with the ``QuerySet`` class for the purpose of understanding
capabilities and limitations of DjangoQuery.

Django provides significant options for adjusting query generation to
fit a specific use case, ``only()``, ``select_related()``,
``prefetch_related()`` are all useful for different cases. Here’s a
point-by-point comparison with Djaq:

-  ``only()``: Djaq always works in “only” mode. Only explicitly
   requested fields are returned.

-  ``select_related()``: The select clause only returns those columns
   explicitly defined. This feature makes loading of related fields
   non-lazy. In contrast, queries are always non-lazy in Djaq.

-  ``prefetch_related()``: When you have a m2m field as a column
   expression, the model hosting that field is repeated in results as
   many times as necessary. Another way is to use a separate query for
   the m2m related records. In anycase, ``prefetch_related()`` this is
   not relevant in Djaq.

-  F expressions: These are QuerySet workarounds for not being able to
   write expressions in the query for things like column value
   arithmetic and other expressions you want to have the db calculate.
   Djaq lets you write these directly and naturally as part of its
   syntax.

-  To aggregate with Querysets, you use ``aggregate()``, whereas Djaq
   aggregates results implicitly whenever an aggregate function appears
   in the column expressions.

-  Model instances with QuerySets exactly represent the corresponding
   Django model. Djaq’s usual return formats, like ``dicts()``,
   ``tuples()``, etc. are more akin to ``QuerySet.value_list()``.

Let’s look at some direct query comparisons:

Get the average price of books:

::

   DQ("(avg(b.price)) Book b")

compared to QuerySet:

::

   Book.objects.all().aggregate(Avg('price'))

Get the difference from the average off the maximum price:

::

   DQ("(Publisher.name, max(Book.price) - avg(Book.price) as price_diff) Book b")

compared to QuerySet:

::

   Book.objects.aggregate(price_diff=Max('price', output_field=FloatField()) - Avg('price'))

Count books per publisher:

::

   DQ("(Publisher.name, count(Book.id) as num_books) Book b")

compared to QuerySet:

::

   Publisher.objects.annotate(num_books=Count("book"))

Count books with ratings up to and over 5:

.. code:: python

   DQ("""(sum(iif(b.rating < 5, b.rating, 0)) as below_5,
       sum(iif(b.rating >= 5, b.rating, 0)) as above_5)
       Book b""")

compared to QuerySet:

.. code:: python

   above_5 = Count('book', filter=Q(book__rating__gt=5))
   below_5 = Count('book', filter=Q(book__rating__lte=5))
   Publisher.objects.annotate(below_5=below_5).annotate(above_5=above_5)

Get average, maximum, minimum price of books:

.. code:: python

   DQ("(avg(b.price), max(b.price), min(b.price)) Book b")

compared to QuerySet:

::

   Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))

Just as there is a ModelInstance class in Django, we have a DQResult
class:

``objs()``: return a DQResult for each result row, basically a namespace
for the object:

.. code:: python

   dq = DQ("(b.id, b.name, Publisher.name as publisher) Book b")
   for book in dq.objs():
       title = book.name
       publisher = book.publisher
       ...

Note that by default, you iterate using a generator. You cannot slice a
generator.

Simple counts:

``DjangoQuery.value()``: when you know the result is a single row with a
single value, you can immediately access it without further iterations:

.. code:: python

   DQ("(count(b.id)) Book b").value()

will return a single integer value representing the count of books.

