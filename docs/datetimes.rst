Datetimes
---------

Datetimes are provided as strings in the iso format that your backend
expects, like ``2019-01-01 18:00:00``.

.. code:: python

    DQ("Book", "pubdate").where("pubdate > '2021-01-01'").go()

Get the difference between two dates:

.. code:: python

    DQ("Book", "pubdate, age({now}, pubdate) as age").context({"now": timezone.now()}).go()

You can access fields of a date, like ``year``, ``month``, ``day``:

.. code:: python

    DQ("Book", "name, publisher.name, pubdate.year").where("pubdate.year < 2022").go()
