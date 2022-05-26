Datetimes
---------

Datetimes are provided as strings in the iso format that your backend
expects, like ``2019-01-01 18:00:00``.

.. code:: python

    DQ("Book", "pubdate").where("pubdate > '2021-01-01'").go()

Get the difference between two dates:

.. code:: python

    now = timezone.now()
    DQ("Book", "pubdate").where("{now}, pubdate").context({"now": now}).go()
