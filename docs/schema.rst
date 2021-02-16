Schema
------

There is a function to get the schema available to a calling client:

.. code:: python

   from djaq.app_utils import get_schema
   print(get_schema())

Pass the same whitelist you use for exposing the query endpoint:

.. code:: python

   wl = {"books": []}
   print(get_schema(whitelist=wl))
