Djaq Management Command
-----------------------

If you include the ``djaq_ui`` app in your INSTALLED_APPS, you have the ``./manage.py djaq`` command at your disposal:

.. code:: shell

    ./manage.py djaq Book --output "pubdate.year" --where "pubdate.year > 2013" --order_by " -pubdate.year" 

Most features are available:

.. code:: shell

    ❯ ./manage.py djaq
    usage: manage.py djaq [-h] [--output OUTPUT] [--where WHERE] [--order_by ORDER_BY] [--format FORMAT] [--schema] [--dataclass] [--limit LIMIT]
                        [--offset OFFSET] [--distinct] [--sql] [--count] [--version] [-v {0,1,2,3}] [--settings SETTINGS] [--pythonpath PYTHONPATH]
                        [--traceback] [--no-color] [--force-color] [--skip-checks]
                        model


Most options are obvious, but some or not related to queries. ``--dataclass`` is
use to generate code for a dataclass corresponding to the given Django model:

.. code:: shell

    ❯ ./manage.py djaq Book --dataclass
    @dataclass
    class BookEntity:
        id: int
        name: str
        pages: int
        price: Decimal
        rating: int
        publisher: int
        alt_publisher: int
        pubdate: datetime.date
        in_print: bool

It's not very sophisticated but should save some typing. 