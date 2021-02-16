
.. image:: images/djaq_ui.png
  :width: 800
  :alt: Alternative text


Quickstart and Installation
---------------------------

You need Python 3.6 or higher and Django 2.1 or higher.

Install:

.. code:: shell

    pip install Djaq


The bleeding edge experience:

.. code:: shell

    pip install https://github.com/paul-wolf/djaq/archive/master.zip


Use:

.. code:: python

    from djaq.query import DjangoQuery as DQ

    print(list(DQ("(b.name as title, b.publisher.name as publisher) Book b").dicts()))

    [{'title': 'Name grow along.', 'publisher': 'Long, Lewis and Wright'}, {'title': 'We pay single record.', 'publisher':\
    'Long, Lewis and Wright'}, {'title': 'Natural develop available manager.', 'publisher': 'Long, Lewis and Wright'}, {'\
    title': 'Fight task international.', 'publisher': 'Long, Lewis and Wright'}, {'title': 'Discover floor phone.', 'publi\
    sher': 'Long, Lewis and Wright'}]

