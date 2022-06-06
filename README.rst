Djaq
====

|Python tests| |RTD build| |Python versions| |PyPi version| 


.. |Python tests| image:: https://github.com/paul-wolf/djaq/actions/workflows/run_unit_tests.yml/badge.svg
   :target: https://github.com/paul-wolf/djaq/actions/workflows/run_unit_tests.yml
   :alt: Unit test status
   
.. |RTD build| image:: https://readthedocs.org/projects/djaq/badge/?version=latest
   :target: https://djaq.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. |Python versions| image:: https://img.shields.io/pypi/pyversions/djaq?color=brightgreen
   :alt: PyPI - Python Version

.. |PyPi version| image:: https://badge.fury.io/py/Djaq.svg
   :target: https://badge.fury.io/py/Djaq
   :alt: PyPi Version

Djaq - pronounced “Jack” - is an alternative to the Django QuerySet API. 

What sets it apart: 

* No need to import models 
* Clearer, more natural query syntax
* More powerful expressions 
* More consistent query syntax without resorting to hacks like ``F()`` expressions, ``annotate()``, ``aggregate()`` 
* Column expressions are entirely evaluated in the database
* Extensible: you can write your own functions
* Pandas: Easily turn a query into Pandas Dataframe

There is also a JSON representation of queries, so you can send queries from a
client. It's an instant API to your data. No need to write backend classes and
serializers.

Djaq queries are strings. A query string for our example dataset might
look like this:

.. code:: shell

   DQ("Book", "name as title, publisher.name as publisher").go()

This retrieves a list of book titles with book publisher. But you can
formulate far more sophisticated queries; see below. You can send Djaq
queries from any language, Java, Javascript, golang, etc. to a Django
application and get results as JSON. In contrast to REST frameworks,
like TastyPie or Django Rest Framework (DRF), you have natural access to
the Django ORM from the client.

Djaq sits on top of the Django ORM. It can happily be used alongside
QuerySets.

-  `Documentation <https://djaq.readthedocs.io>`__
-  `Installation <https://djaq.readthedocs.io/en/latest/installation.html>`__
-  `Settings <https://djaq.readthedocs.io/en/latest/settings.html>`__
-  `Query
   Usage <https://djaq.readthedocs.io/en/latest/query_usage.html>`__
-  `Sample
   Project <https://djaq.readthedocs.io/en/latest/sample_project.html>`__

Here's an example comparison between Djaq and Django QuerySets:

.. code:: python

   DQ("Book", """
       sumif(rating < 3, rating, 0) as below_3,
       sumif(rating >= 3, rating, 0) as above_3
       """)

compared to QuerySet:

.. code:: python
   
   from django.db.models import Count, Q
   above_3 = Count('book', filter=Q(book__rating__gt=3))
   below_3 = Count('book', filter=Q(book__rating__lte=3))
   Publisher.objects.annotate(below_3=below_3).annotate(above_3=above_3)

Get average, maximum, minimum price of books:

.. code:: python

   DQ("Book", "avg(price), max(price), min(price)")

compared to QuerySet:

.. code:: python

   Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))

Get the difference from the average off the maximum price:

.. code:: python

   DQ("Book", "publisher.name, max(price) - avg(price) as price_diff")

compared to QuerySet:

.. code:: python

   from django.db.models import FloatField, Avg, Max
   Book.objects.values("publisher__name")
      .annotate(price_diff=Max('price', output_field=FloatField()) - Avg('price', output_field=FloatField()))
