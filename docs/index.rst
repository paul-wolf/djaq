Introduction to Djaq
====================

Djaq - pronounced “Jack” - is an alternative to the Django QuerySet API. 

What sets it apart: 

- No need to import models 
- Clearer, more natural query syntax
- More powerful expressions for output
- More powerful, easier-to-write filter expressions
- More consistent query syntax without resorting to hacks like ``F()`` expressions, ``annotate()``, ``aggregate()`` 
- Column expressions are entirely evaluated in the database
- Extensible: you can write your own functions
- Pandas: Easily turn a query into a Pandas Dataframe

There is also a JSON representation of queries, so you can send queries from a
client. It's an instant API to your data. No need to write backend classes and
serializers.

Djaq queries are strings. A query string for our example dataset might
look like this:

.. code:: shell

   DQ("Book", "name as title, publisher.name as publisher").go()

This retrieves a list of book titles with book publisher. But you can formulate
far more sophisticated queries; see below. You can send Djaq queries from any
language, Java, Javascript, golang, etc. to a Django application and get results
as JSON. In contrast to REST frameworks, you have natural access to the Django
ORM from the client.

Djaq sits on top of the Django ORM. It can happily be used alongside
QuerySets.


.. toctree::
   :maxdepth: 3
   :caption: Contents:

   installation
   settings
   query_usage
   api_reference
   management_command
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
   schema
   querysets
   .. outerref
   context_validators
   query_ui
   custom_api
   .. other_frameworks
   limitations
   performance
   sample_project

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

