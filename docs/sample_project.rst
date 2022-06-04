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
softlink. Create the virtualenv:

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

So, it assumes peer authentication. Change to suit your needs. Now you
can migrate. Make sure the virtualenv is activated!

::

   ./manage.py migrate

We provide a script to create some sample data:

::

   ./manage.py build_data --book-count 2000

This creates 2000 books and associated data.

There's a management command to run queries from the command line:

::

   ./manage.py djaq Book

Output of the command should look like this:

::

   ❯ ./manage.py djaq Book
   [
      {
         "id": 2,
         "name": "Station many chair pressure.",
         "pages": 414,
         "price": "12.00",
         "rating": 2.0,
         "publisher": 99,
         "alt_publisher": null,
         "pubdate": "2016-11-30",
         "in_print": true
      },
      {
         "id": 3,
         "name": "Able sense quickly.",
         "pages": 408,
         "price": "29.00",
         "rating": 3.0,
         "publisher": 40,
         "alt_publisher": null,
         "pubdate": "2001-07-27",
         "in_print": true
      },
      ...

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
