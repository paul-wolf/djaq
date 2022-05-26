Order by
--------

You can order_by like this:

.. code:: python

   DQ("Book", "id").where("price > 20").order_by("name")

Descending order:

.. code:: python

   DQ("Book", "id").where("price > 20").order_by("-name")

You can have multple order by expressions.

.. code:: python

   DQ("Book", "name, publisher.name").where("price > 20").order_by("-name, publisher.name")
