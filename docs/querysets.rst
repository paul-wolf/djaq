Comparing to Django QuerySets
=============================

Djaq can be used in theory as a total replacement for `Django QuerySets
<https://docs.djangoproject.com/en/3.1/ref/models/querysets/>`_


Djaq has some important advantages over QuerySets. You will probably find Djaq
queries easier to write and understand. 

Djaq queries are easier to understand because they don't make you jump around
mentally parsing the difference between ``_`` and ``__`` and there are far fewer
"special cases" where you need to use different classes and functions to overcome
syntactical constraints of QuerySets.

You can send Djaq queries over the wire for a remote api with minimal effort,
like via a REST call, and receive JSON results. That's not possible with
QuerySets.

Djaq is explicit about performance semantics. In contrast you need to have
knowledge of and use QuerySets carefully to avoid performance pitfalls. 

This section is intended to highlight differences for users with good
familiarity with the ``QuerySet`` class for the purpose of comparing
``DjaqQuery`` and ``QuerySet``.

Django provides significant options for adjusting query generation to
fit different use cases, ``only()``, ``select_related()``,
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

-  To aggregate with Querysets, you use ``aggregate()``, or ``annotate()`` whereas Djaq
   aggregates results whenever an aggregate function appears
   in a column expression, just like you would expect it to.

-  Model instances with QuerySets exactly represent the corresponding Django
   model. Djaq’s usual return formats, like ``dicts()``, ``tuples()``, etc. are
   more akin to ``QuerySet.values()`` and ``QuerySet.value_list()``.

- Slicing: QuerySets can bet sliced: ``qs[100:150]`` whereas you use
  ``limit()``, ``offset()`` with Djaq: ``dq.offset(100).limit(50)``

- Caching: QuerySets will cache results in a rather sophisticated manner to
  support slicing (above). With Djaq, you need to rerun the query each time
  unless you are caching results yourself. Djaq eschews caching as part of the
  query evaluation to encourage separation of concerns and prevent unintended
  performance results.

Filter expressions in Djaq have a single expression paradigm, unlike QuerySets.
When you filter a QuerySet, because you are assigning values to a series of
parameters, the only way to construct the final SQL WHERE is to logically
conjoin the boolean assertions. 

.. code:: python

   Book.objects.filter(name_startswith="Bar", pubdate__year__gt='2020') 

means ``name ILIKE 'Bar%' AND date_part("year", pubdate) > 2020``. Whereas Djaq is explicit:

.. code:: python

   DQ("Book").where("ilike(name, 'Bar*') and pubdate.year > 2020")

If you want to change your query to ``OR`` with querysets, you have to change how you construct the filter:

.. code:: python

   from django.db.models import Q
   Book.objects.filter(Q(name_startswith="Bar") | Q(pubdate__year__gt=2020)) 

with Djaq, you just do the obvious, change the operator:

.. code:: python

   DQ("Book").where("ilike(name, 'Bar%') or pubdate.year > 2020")

Both QuerySets and DjaqQuerys let you add conditions incrementally: 

.. code:: python

   DQ("Book").where("regex(name, 'B.*')").where("pubdate.year > 2020")

   Book.objects.filter(name__startswith="B").filter(pubdate__year__gt='2020')

The presumption is to conjoin the two conditions with "AND" in both cases.

Let’s look at some more query comparisons:

Get the average price of books:

.. code:: python

   DQ("Book","avg(price)").value()

compared to QuerySet:

.. code:: python

   Book.objects.aggregate(Avg('price'))

Get the difference from the average off the maximum price for each publisher: 

.. code:: python

   DQ("Book", "publisher.name, max(price) - avg(price) as price_diff")

compared to QuerySet:

.. code:: python

   from django.db.models import Avg, Max
   Book.objects.values("publisher__name").annotate(price_diff=Max('price') - Avg('price'))

Count books per publisher:

.. code:: python

   DQ("Publisher", "name as publisher, count(book) as num_books")

compared to QuerySet:

.. code:: python

   Publisher.objects.annotate(num_books=Count("book"))

Count books with ratings up to and over a number:

.. code:: python

   DQ("Book", """publisher.name,
       sumif(rating <= 3, rating, 0) as below_3,
       sumif(rating > 3, rating, 0) as above_3
       """).go()

compared to QuerySet:

.. code:: python

   from django.db.models import Count, Q
   below_3 = Count('book', filter=Q(book__rating__lte=3))
   above_3 = Count('book', filter=Q(book__rating__gt=3))
   Publisher.objects.annotate(below_3=below_3).annotate(above_3=above_3)

Get average, maximum, minimum price of books:

.. code:: python

   DQ("Book", "avg(price), max(price), min(price)")

compared to QuerySet:

.. code:: python

   Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))

Note that by default, you iterate using a generator. You cannot slice a
generator. Use ``limit()`` and ``offset()`` to page results

Simple counts:

``DjaqQuery.value()``: when you know the result is a single row with a
single value, you can immediately access it without further iterations:

.. code:: python

   DQ("Book", "count(id)").value()

will return a single integer value representing the count of books.

