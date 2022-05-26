Introduction to Djaq
====================

Djaq - pronounced "Jack" - provides an instant remote API to your
`Django <https://www.djangoproject.com/>`_ models data with a powerful query language. No server-side code
beyond two lines of config is required. You don't write backend
classes, serializers or any other code to be able to immediately get
whatever data you want to the client. And it is blazing fast.

Djaq queries are strings. A query string for our example dataset might
look like this:

.. code:: python

    DQ("Book", "name as title, publisher.name as publisher")

This retrieves a list of book titles with book publisher. But you can
formulate far more sophisticated queries, see below. You can send Djaq
queries from any language, Java, Javascript, golang, etc. to a Django
application and get results as JSON. In contrast to REST frameworks,
like TastyPie or Django Rest Framework (DRF), you have natural access
to the Django ORM from the client.

Djaq is a good fit if you want:

* Microservice communication where some services don't have access to
  the Django ORM or are not implemented with Python

* Fast local UI development

* Fast development of Proof of Concepts

Djaq sits on top of the Django ORM. It can happily be used alongside
QuerySets and sometimes calling a Djaq query even locally might be
preferable to constructing a Queryset, although Djaq is not a
replacement for QuerySets.

Features you might appreciate:

* Immediate gratification with zero or minimal server-side
  code. Because there is minimal setup, there is minimal wasted effort
  if you later move to another framework, like GraphQL or DRF. But
  getting started calling your API is much faster than those
  frameworks.

* A natural syntax that lets you compose queries using Python-like
  expressions. The query format and syntax is designed to be written by
  hand quickly. Readability is a key goal.

* Complex expressions let you push computation down to the database
  layer from the client easily.

* Fast cursor semantics and explicit retrieval. It only gets data you
  asked for.

* Obvious performance behaviour. It will trigger a query in one
  obvious way through one of the generator methods: `.dicts()`,
  `.tuples()`, `.json()`.

* A ready-to-go CRUD API that is easy to use. You can send requests to
  have an arbitrary number of Create, Read, Write, Delete operations
  done in a single request.

* Customisable behaviour using your own functions and data validators.

* A handy user interface for trying out queries on your data models.

Djaq provides whitelisting of apps and models you want to expose. It
also provides a simple permissions scheme via settings.

.. toctree::
   :maxdepth: 3
   :caption: Contents:

   installation
   settings
   query_usage
   results
   pandas
   conditions
   functions
   column_expressions
   subqueries
   order_by
   constants
   datetimes
   count
   slicing
   rewind_cursor
   schema
   querysets
   outerref
   context_validators
   query_ui
   custom_api
   other_frameworks
   limitations
   performance
   sample_project

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

