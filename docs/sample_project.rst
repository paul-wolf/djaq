Sample Bookshop Project
=======================

If you want to use Djaq right away in your own test project and you feel
confident, crack on. In that case skip the following instructions for
using the sample Bookshop project. Or, if you want to try the sample
project, clone the django repo:

::

   git clone git@github.com:paul-wolf/djaq.git
   cd djaq/bookshop

If you clone the repo and use the sample project, you don’t need to
include Djaq as a requirement because it’s included as a module by a
softlink. 

The module itself does not install Django and there are no further
requirements. Make sure you are in the ``bookshop`` directory:

.. code:: shell

   python -m venv .venv && source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

We need a log directory:

.. code:: shell

   mkdir log

Create a user. Let’s assume a super user:

.. code:: shell

   createsuperuser --username yourname

Now make sure there is a Postgresql instance running. The settings are
like this:

.. code:: python

   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql_psycopg2',
           'NAME': 'bookshop',
       },
   }

So, it assumes peer authentication. Change to suit your needs. Now you
can migrate. Make sure the virtualenv is activated!

::

   ./manage.py migrate

We provide a script to create some sample data:

::

   ./manage.py build_data --book-count 2000

This creates 2000 books and associated data.

The example app comes with a management command to run queries:

::

   ./manage.py djaq "(Publisher.name, max(Book.price) - round(avg(Book.price)) as diff) Book b"  --format json

Output of the command should look like this:

::

   ▶ ./manage.py djaq "(Publisher.name, max(Book.price) - round(avg(Book.price)) as diff) Book b"  --format json
   SELECT books_publisher.name, (max(books_book.price) - round(avg(books_book.price))) FROM books_book LEFT JOIN books_publisher ON (books_book.publisher_id = books_publisher.id)  GROUP BY books_publisher.name LIMIT 10
   {"publisher_name": "Avila, Garza and Ward", "diff": 14.0}
   {"publisher_name": "Boyer-Clements", "diff": 16.0}
   {"publisher_name": "Clark, Garza and York", "diff": 15.0}
   {"publisher_name": "Clarke PLC", "diff": 14.0}
   {"publisher_name": "Griffin-Blake", "diff": 16.0}
   {"publisher_name": "Hampton-Davis", "diff": 13.0}
   {"publisher_name": "Jones LLC", "diff": 15.0}
   {"publisher_name": "Lane-Kim", "diff": 15.0}
   {"publisher_name": "Norris-Bennett", "diff": 14.0}
   {"publisher_name": "Singleton-King", "diff": 17.0}

Notice the SQL used to retrieve data is printed first.

The best approach now would be to trial various queries using the Djaq
UI as explained above.

Finally, checkout the settings for the bookshop. You will notice that
many admin models are not accessible. In a real application we’d want to
prevent access to user data and other data on perhaps a finer grained
level.

Run the server:

.. code:: shell

   ./manage.py runserver

Now the query UI should be available here:

http://127.0.0.1:8000/dquery/


There is a sample UI at http://localhost:8000/books/books/ that demonstrates a
view function using a conditional expression like the following:

.. code:: python

   c = (
      B("regex(b.name, '$(name)')")
      & B("b.pages > '$(pages)'")
      & B("b.rating > '$(rating)'")
      & B("b.price > '$(price)'")
   )

to search for books based on the form input. 

