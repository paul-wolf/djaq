Order by
--------

You can order_by like this:

::

   DQ("(b.id) Book{b.price > 20} b order by (b.name)")

Descending order:

::

   DQ("(b.id) Book{b.price > 20} b order by (-b.name)")

You can have multple order by expressions.

::

   DQ("(b.name, Publisher.name) Book{b.price > 20} b order by (-b.name, b.publisher.name)")
