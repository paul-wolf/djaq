Comparing to Django QuerySets
=============================

Djaq can be used in theory as a total replacement for `Django QuerySets
<https://docs.djangoproject.com/en/3.1/ref/models/querysets/>`_

However, a couple things should be kept in mind. Firstly, Querysets are highly
integrated with Django and have been developed over 15 years by many developers.
If you use the QuerySet API to access data via the Models you specified, you
are working within the Django framework the way it was intended.

That being said, Djaq has some important advantages over QuerySets: 

* If you are not thoroughly familiar with the QuerySet api, you might find Djaq
  queries easier to understand and write. 
  
* You can send Djaq queries over the wire for a remote api with minimal effot, like
  via a REST call, and receive JSON results. That's not possible with QuerySets.

* Djaq is explicit about performance semantics. In contrast you need to have
  knowledge of and use QuerySets carefully to avoid performance pitfalls. 

This section is intended to highlight differences for users with good
familiarity with the ``QuerySet`` class for the purpose of understanding
capabilities and limitations of the DjaqQuery.

Django provides significant options for adjusting query generation to
fit a specific use case, ``only()``, ``select_related()``,
``prefetch_related()`` are all useful for different cases. Here’s a
point-by-point comparison with Djaq:

-  ``only()``: Djaq always works in “only” mode. Only explicitly requested
   fields are returned with the exception of providing no output fields in which
   case Djaq produces all fields but with no foreign key relations. 

-  ``select_related()``: The output field expression list only returns those columns
   explicitly defined. This feature makes loading of related fields
   non-lazy. In contrast, queries are always non-lazy in Djaq.

-  ``prefetch_related()``: When you have a m2m field as a column
   expression, the model hosting that field is repeated in results as
   many times as necessary. Another way is to use a separate query for
   the m2m related records. In any case, ``prefetch_related()`` is
   not relevant in Djaq.

-  ``F`` expressions: These are QuerySet workarounds for not being able to
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

.. code:: python

   DQ("Book","avg(price)").value()

compared to QuerySet:

.. code:: python

   Book.objects.all().aggregate(Avg('price'))

Get the difference from the average off the maximum price:

.. code:: python

   DQ("Book", "publisher.name, max(price) - avg(price) as price_diff")

compared to QuerySet:

.. code:: python

   Book.objects.values("publisher__name")
      .annotate(price_diff=Max('price', output_field=FloatField()) - Avg('price', output_field=FloatField()))

Count books per publisher:

.. code:: python

   DQ("Publisher", "name, count(books) as num_books")

compared to QuerySet:

.. code:: python

   Publisher.objects.annotate(num_books=Count("book"))

Count books with ratings up to and over a number:

.. code:: python

   DQ("Book", """
       sum(iif(rating < 3, rating, 0)) as below_3,
       sum(iif(rating >= 3, rating, 0)) as above_3
       """)

compared to QuerySet:

.. code:: python

   above_3 = Count('book', filter=Q(book__rating__gt=3))
   below_3 = Count('book', filter=Q(book__rating__lte=3))
   Publisher.objects.annotate(below_3=below_3).annotate(above_3=above_3)

Get average, maximum, minimum price of books:

.. code:: python

   DQ("Book", "avg(price), max(price), min(price)")

compared to QuerySet:

.. code:: python

   Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))


Note that by default, you iterate using a generator. You cannot slice a
generator.

Simple counts:

``DjaqQuery.value()``: when you know the result is a single row with a
single value, you can immediately access it without further iterations:

.. code:: python

   DQ("Book", "count(id)").value()

will return a single integer value representing the count of books.

