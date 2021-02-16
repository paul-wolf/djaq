Query usage guide
-----------------

Throughout, we use models somewhat like those from Django’s bookshop
example:

.. code:: python

   from django.db import models

   class Author(models.Model):
       name = models.CharField(max_length=100)
       age = models.IntegerField()

   class Publisher(models.Model):
       name = models.CharField(max_length=300)

   class Book(models.Model):
       name = models.CharField(max_length=300)
       pages = models.IntegerField()
       price = models.DecimalField(max_digits=10, decimal_places=2)
       rating = models.FloatField()
       authors = models.ManyToManyField(Author)
       publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
       pubdate = models.DateField()

   class Store(models.Model):
       name = models.CharField(max_length=300)
       books = models.ManyToManyField(Book)

These examples use auto-generated titles and names and we have a
slightly more complicated set of models than shown above.

Let’s get book title (name), price, discounted price, amount of discount
and publisher name wherever the price is over 50.

.. code:: python

   result = \
     list(DQ("""(b.name,
       b.price as price,
       0.2 as discount,
       b.price * 0.2 as discount_price,
       b.price - (b.price*0.2) as diff,
       Publisher.name
     ) Book{b.price > 50} b""").dicts())

``result`` now contains a list of dicts each of which is a row in the
result set. One example:

.. code:: python

   [{'b_name': 'Address such conference.',
     'price': Decimal('99.01'),
     'discount': Decimal('0.2'),
     'discount_price': Decimal('19.802'),
     'diff': Decimal('79.208'),
     'publisher_name': 'Arnold Inc'}]

Here is the structure of the syntax:

.. code:: shell

   (<field_exp1>, ...) <ModelName>{<filter_expression>} <alias> order by (<field_exp1>, ...)

Whitespace does not matter too much. You could put things on separate
lines:

.. code:: shell

   (
      b.name, b.price,
      Publisher.name
   )
   Book{p.price > 50} b

Always start with column expressions you want to return in parens:

.. code:: shell

   (b.name, b.price, Publisher.name)

These expressions can be Django Model fields or arithmetic expressions
or any expression supported by functions of your underlying database
that are also whitelisted by Djaq. Postgresql has thousands of
functions. About 350 of those are available in Djaq.

Columns are automatically given names. But you can give them your own
name:

.. code:: shell

   (b.name as title, b.price as price, Publisher.name as publisher)

Next is the model alias declaration:

.. code:: shell

   Book b

or if we want to filter and get only books over 50 in price:

.. code:: shell

   Book{b.price > 50} b

``Book`` is the Django Model name. ``b`` is an alias we can use as an
abbreviation in the filter or returned column expressions. We put the
filter in curly braces, ``{}``, between the model name and alias. Use
Python syntax to express the filter. Also use Python syntax to express
the data to return. You don’t have access to the Python Standard
Library. This is basically the intersection of SQL and Python:

The following filter:

::

   {b.price > 50 and ilike(Publisher.name, 'A%')}

will be translated to SQL:

::

   b.price > 50 AND publisher.name ILIKE 'A%'

The expressions are fully parsed so they are not subject to SQL
injection. Trying to do so will cause an exception.

You might notice in the above examples, Publisher does not use an alias.
If you wanted an alias for Publisher, you could use a more complicated
syntax:

.. code:: shell

   (b.name, b.price) Book b
   -> (p.name) Publisher.name p

Notice, we use the ``->`` symbol to add another aliased relationship.
This is one of three options: ``->``, ``<-``, ``<>`` that indicate you
want to explicitly join via an SQL LEFT, RIGHT or INNER join
respectively. But you don’t need to do this. LEFT joins will always be
implicit. We did not even need to refer to the Publisher model directly.
We could have done this:

::

   (b.name, b.price, b.publisher.name as publisher)
   Book{p.price > 50} b

Our example model also has an owner model called “Consortium” that is
the owner of the publisher:

.. code:: python

   In [16]: print(list(DQ("(b.name, b.price, b.publisher.name, b.publisher.owner.name) Book b").limit(1).dicts()))
   Out[16]: [{'b_name': 'Range total author impact.', 'b_price': Decimal('12.00'), 'b_publisher_name': 'Wright, Taylor and Fitzpatrick', 'b_publisher_owner_name': 'Publishers Group'}]

To recap, there are three alternative patterns to follow to get the
publisher name in the result set:

.. code:: python

   In [13]: print(list(DQ("(b.name, b.price) Book b -> (p.name)Publisher p").limit(1).dicts()))

   In [14]: print(list(DQ("(b.name, b.price, Publisher.name) Book b").limit(1).dicts()))

   In [15]: print(list(DQ("(b.name, b.price, b.publisher.name) Book b").limit(1).dicts()))

Note that the above will each produce slightly different auto-generated
output names unless you provide your own aliases.

Signal that you want to summarise results using an aggregate function:

.. code:: python

   list(DQ("(b.publisher.name as publisher, count(b.id) as book_count) Book b").dicts())

   [
       {
           "publisher": "Martinez, Clark and Banks",
           "book_count": 6
       },
       {
           "publisher": "Fischer-Casey",
           "book_count": 9
       },
       etc.
   ]

Order by name:

::

   (b.name, b.price, b.publisher.name as publisher)
   Book{p.price > 50} b
   order by (b.name)

The parentheses around the order by expression are required.

Get average, minimum and maximum prices:

.. code:: python

   list(DQ("(avg(b.price) as average, min(b.price) as minimum, max(b.price) as maximum) Book b").dicts())
   [
      {
         "average": "18.5287169247794985",
         "minimum": "3.00",
         "maximum": "99.01"
      }
   ]

Count all books:

.. code:: python

   list(DQ("(count(b.id)) Book b").dicts())

   [
       {
           "countb_id": 149999
       }
   ]

You can qualify model names with the app name or registered app path:

::

   (b.name, b.publisher.name) books.Book b

You’ll need this if you have models from different apps with the same
name.

To pass parameters, use variables in your query, like ``'$(myvar)'``:

.. code:: pycon

   In [30]: oldest = '2018-12-20'
       ...: list(DQ("(b.name, b.pubdate) Book{b.pubdate >= '$(oldest)'} b").context({"oldest": oldest}).limit(5).tuples())
   Out[30]:
   [('Available exactly blood.', datetime.date(2018, 12, 20)),
    ('Indicate Congress none always.', datetime.date(2018, 12, 24)),
    ('Old beautiful three program.', datetime.date(2018, 12, 25)),
    ('Oil onto mission.', datetime.date(2018, 12, 21)),
    ('Key same effect me.', datetime.date(2018, 12, 23))]

Notice that the variable holder, ``$()``, *must* be in single quotes.
