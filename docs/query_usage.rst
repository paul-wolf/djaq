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

The first thing you want to do is import the DjangoQuery class which we do with an alias:

.. code:: python

   from djaq import DjangoQuery as DQ

Let’s get book title (name), price, discounted price, amount of discount
and publisher name wherever the price is over 50.



.. code:: python

   result = \
     list(DQ("Book", """name,
       price as price,
       0.2 as discount,
       price * 0.2 as discount_price,
       price - (price*0.2) as diff,
       publisher.name
       """
     ).where("price > 5").dicts())

``result`` now contains a list of dicts each of which is a row in the
result set. One example:

.. code:: python

   [{'name': 'Address such conference.',
     'price': Decimal('99.01'),
     'discount': Decimal('0.2'),
     'discount_price': Decimal('19.802'),
     'diff': Decimal('79.208'),
     'publisher_name': 'Arnold Inc'}]

Here is the structure of the syntax:

.. code:: shell

   DjaqQuery([model_name|model], [<field_exp1>, ...])
   .where(<condition_expression>)
   .order_by(<field_exp1>, ...)

Whitespace does not matter too much. You could put things on separate
lines.

Note as well that we usually in this tutorial use the `.go()` convenience
method. The following two calls are pretty much equivalent:

.. code:: shell

   DQ("Book", "name").go()

   list(DQ("Book", "name").dicts())

The column expressions can be Django Model fields or arithmetic expressions
or any expression supported by functions of your underlying database
that are also whitelisted by Djaq. Postgresql has thousands of
functions. About 350 of those are available in Djaq.

Columns are automatically given names. But you can give them your own
name:

.. code:: shell

   DQ("Book", "name as title, price as price, publisher.name as publisher").go()

or if we want to filter and get only books over 5 in price:

.. code:: shell

   DQ("Book", "name as title, price as price, publisher.name as publisher") \
      .where("price > 5") \
      .go()



The following filter:

.. code:: shell

   DQ("Book").where("price > 5 and ilike(publisher.name, 'A%')").go()

will be translated to SQL:

.. code:: sql

   Book.price > 50 AND Publisher.name ILIKE 'A%'

The expressions are fully parsed so they are not subject to SQL
injection.

Our example model also has an owner model called “Consortium” that is
the owner of the publisher:

.. code:: python

   DQ("Book", "name, price, publisher.name, publisher.owner.name").limit(1).go()
   [{'b_name': 'Range total author impact.', 'b_price': Decimal('12.00'), 'b_publisher_name': 'Wright, Taylor and Fitzpatrick', 'b_publisher_owner_name': 'Publishers Group'}]


Signal that you want to summarise results using an aggregate function:

.. code:: python

   DQ("Book", "publisher.name as publisher, count(id) as book_count").go()

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

.. code:: python

    DQ("Book", "name, price, publisher.name as publisher") \
    .where("price > 5") \
    .order_by("name") \
    .go()

Get average, minimum and maximum prices:

.. code:: python

   DQ("Book", "avg(price) as average, min(price) as minimum, max(price) as maximum").go()
   [
      {
         "average": "18.5287169247794985",
         "minimum": "3.00",
         "maximum": "99.01"
      }
   ]

Count all books:

.. code:: python

   DQ("Book", "count(id)").value()

   1000

You can qualify model names with the app name or registered app path:

.. code:: python

   DQ("books.Book", "name, publisher.name")

You’ll need this if you have models from different apps with the same
name.

To pass parameters, use variables in your query, like ``{myvar}``:

.. code:: python 

   In [30]: oldest = '2018-12-20'
       ...: list(DQ("Book", "name, pubdate").where("pubdate >= {oldest}").context({"oldest": oldest}).limit(5).tuples())
   Out[30]:
   [('Available exactly blood.', datetime.date(2018, 12, 20)),
    ('Indicate Congress none always.', datetime.date(2018, 12, 24)),
    ('Old beautiful three program.', datetime.date(2018, 12, 25)),
    ('Oil onto mission.', datetime.date(2018, 12, 21)),
    ('Key same effect me.', datetime.date(2018, 12, 23))]

Notice that variables are not f-string placeholders! Avoid using f-strings to
interpolate arguments as that puts you at risk of sql injection.
