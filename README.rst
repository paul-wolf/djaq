Djaq
====

Djaq - pronounced “Jack” - provides an instant remote API to your Django
models data with a powerful query language. No server-side code beyond
two lines of config is required. You don’t write backend classes,
serializers or any other code to be able to immediately get whatever
data you want to the client. And it is blazing fast.

Djaq queries are strings. A query string for our example dataset might
look like this:

.. code:: shell

   (b.name as title, b.publisher.name as publisher) Book b

This retrieves a list of book titles with book publisher. But you can
formulate far more sophisticated queries, see below. You can send Djaq
queries from any language, Java, Javascript, golang, etc. to a Django
application and get results as JSON. In contrast to REST frameworks,
like Django Rest Framework (DRF), you have natural access to the Django
ORM from the client.

-  `Documentation <https://djaq.readthedocs.io>`__
-  `Installation <https://djaq.readthedocs.io/en/latest/installation.html>`__
-  `Settings <https://djaq.readthedocs.io/en/latest/settings.html>`__
-  `Query
   Usage <https://djaq.readthedocs.io/en/latest/query_usage.html>`__
-  `Sample
   Project <https://djaq.readthedocs.io/en/latest/sample_project.html>`__

Djaq is a good fit if you want:

-  A fast, natural query language with great performance

-  Fast UI development

-  Fast development of Proof of Concepts

-  Microservice communication where some services don’t have access to
   the Django ORM or are not implemented with Python

Djaq sits on top of the Django ORM. It can happily be used alongside
QuerySets and sometimes calling a Djaq query even locally might be
preferable to constructing a Queryset, although Djaq is not a direct
replacement for QuerySets. You can even combine Djaq queries and
Querysets.

Features you might appreciate:

-  Immediate gratification with zero or minimal server-side code.
   Because there is minimal setup, there is minimal wasted effort if you
   later move to another framework, like GraphQL or DRF. But getting
   started calling your API is much faster than those frameworks.

-  A natural syntax that lets you compose queries using Python-like
   expressions. The query format and syntax is designed to be written by
   hand quickly. Readability is a key goal.

-  Complex expressions let you push computation down to the database
   layer from the client easily.

-  Fast cursor semantics and explicit retrieval. It only gets data you
   asked for.

-  Obvious performance behaviour. It will trigger a query in one obvious
   way through one of the generator methods: ``.dict()``, ``.tuples()``,
   ``.json()``.

-  A ready-to-go CRUD API that is easy to use. You can send requests to
   have an arbitrary number of Create, Read, Write, Delete operations
   done in a single request.

-  Customisable behaviour using your own functions and data validators.

-  A handy user interface for trying out queries on your data models.

Djaq provides whitelisting of apps and models you want to expose. It
also provides a simple permissions scheme via settings.

.. figure:: bookshop/screenshots/djaq_ui.png?raw=true
   :alt: Djaq UI

   Djaq UI
