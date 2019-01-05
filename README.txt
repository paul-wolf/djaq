Djaq: Django Queries
====================

copyright (c) Paul Wolf

To Install:

::

    git clone git@github.com:paul-wolf/djaq.git
    cd djaq

Create the virtualenv:

::

    virtualenv -p python3 .venv    

Activate the virtual environment:

::

    source ../.venv/bin/activate

The module itself does not install Django and there are no further
requirements. The example Django application is in ./bookshop. To
install dependencies for the sample application:

::

    cd bookshop
    pip install -r requirements.txt

Make sure the virtualenv is activated! The sample database is already
part of source code now (sqlite). The example application comes with a
management command to run queries:

::

    ./manage.py djaq "(Publisher.name, max(Book.price) - round(avg(Book.price)) as diff) Book b"  --format json

If using in code, you would do this:

::

    from xquery.exp import XQuery as XQ
    xq = XQ("(avg(b.price) as average_book_price) Book b"
    print(xq.json())

There are several generators to choose from to iterate records:

::

    XQuery.json()  # return json objects
    XQuery.dicts() # dicts
    XQuery.tuples() # tuples of values
    XQuery.objs()  # We return for each record, an instance of XQueryInstance

The XQueryInstance is basically a namespace so you can do this:

::

    for inst in XQ('(Book.name, Book.price)').objs():
        print(inst.name)
        print(inst.price)

etc.

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

The syntax is like this:

::

    <join_operator> (<column_exp>, ... ) ModelName{<filter_expression>} Alias

Most of these are optional. You don’t have to reference models in an
expression with Alias; you don’t need a filter in curly braces, etc.
There is no point in providing the join_operator on the first relation.
You can have as many of these as you wish to add more relations. You can
even skip the join relation on subsequent relations: it will default to
LEFT JOIN. Don’t bother doing this:

::

    (Books.name, Publisher.name) Book -> Publisher

because you can just do this:

::

    (Books.name, Publisher.name) Book

It will know to create the join to Publisher. But you might want to
include it for the purpose of having an alias for Publisher:

::

    (b.name, p.name) Book b -> Publisher p

Use “as” operator to name columns:

::

    (b.name as book_name, p.name as publisher) Book b -> Publisher p

Get the average price of books for each publisher:

::

    (avg(b.price)) Book b

Get the difference off the maximum price:

::

    (Publisher.name, max(Book.price) - avg(Book.price) as diff) Book b

Count books per publisher:

::

    (Publisher.name, count(Book.id) as num_books) Book b

Count books with ratings up to and over 3:

::

    (sum(b.rating > 3), sum(b.rating <= 3)) Book b

Get average, maximum, minimum price of books:

::

    (avg(b.price), max(b.price), min(b.price)) Book b

##TODO

-  Improve group by detection
-  Reference named xqueries as relations (for subqueries)
-  IN operator either subquery, list, m2m, QuerySet
-  startswith, endswith custom functions etc.
-  m2m field relations
-  backwards relations
-  subquery, outter reference
-  map/reduce
-  Native sql backticks
-  Parameter checking and type casting
-  Emit names in double quotes
-  CSV import
   https://github.com/edcrewe/django-csvimport/blob/master/csvimport/parser.py
-  format sql https://pypi.org/project/format-sql/
