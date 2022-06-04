Djaq
====

Djaq - pronounced “Jack” - is an alternative to the Django QuerySet API. 

What sets it apart: 

* No need to import models 
* Clearer, more natural query syntax
* More powerful expressions 
* More consistent query syntax without resorting to hacks like ``F()`` expressions, ``annotate()``, ``aggregate()`` 
* Column expressions are entirely evaluated in the database
* Extensible: you can write your own functions

There is also a JSON representation of queries, so you can send queries from a
client. It's an instant API to your data. No need to write backend classes and
serializers.

Djaq queries are strings. A query string for our example dataset might
look like this:

.. code:: shell

   DQ("Book", "name as title, publisher.name as publisher").go()

This retrieves a list of book titles with book publisher. But you can
formulate far more sophisticated queries; see below. You can send Djaq
queries from any language, Java, Javascript, golang, etc. to a Django
application and get results as JSON. In contrast to REST frameworks,
like TastyPie or Django Rest Framework (DRF), you have natural access to
the Django ORM from the client.

Djaq sits on top of the Django ORM. It can happily be used alongside
QuerySets and sometimes calling a Djaq query even locally might be
preferable to constructing a Queryset, although Djaq is not a
replacement for QuerySets.

Features you might appreciate:

-  Immediate gratification with zero or minimal server-side code.
   Because there is minimal setup, there is minimal wasted effort if you
   later move to another framework, like GraphQL or DRF. But getting
   started calling your API is much faster than those frameworks.

-  A natural syntax that lets you compose queries using Python-like
   expressions. The query format and syntax is designed to be written by
   hand quickly. Readability is a key goal.

-  Complex expressions let you push computation down to the database
   layer from the client easily.

-  Fast cursor semantics and explicit retrieval. It only gets data you
   asked for.

-  Obvious performance behaviour. It will trigger a query in one obvious
   way through one of the generator methods: ``.dict()``, ``.tuples()``,
   ``.json()``.

-  A ready-to-go CRUD API that is easy to use. You can send requests to
   have an arbitrary number of Create, Read, Write, Delete operations
   done in a single request.

-  Customisable behaviour using your own functions and data validators.

-  A handy user interface for trying out queries on your data models.

Djaq provides whitelisting of apps and models you want to expose. It
also provides a simple permissions scheme via settings.

.. figure:: bookshop/screenshots/djaq_ui.png?raw=true
   :alt: Djaq UI

   Djaq UI

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

   DQ("Book", "name as title, publisher.name as publisher").go()

   [{'title': 'Name grow along.', 'publisher': 'Long, Lewis and Wright'}, {'title': 'We pay single record.', 'publisher': 'Long, Lewis and Wright'}, {'title': 'Natural develop available manager.', 'publisher': 'Long, Lewis and Wright'}, {'title': 'Fight task international.', 'publisher': 'Long, Lewis and Wright'}, {'title': 'Discover floor phone.', 'publisher': 'Long, Lewis and Wright'}]

Providing an API
----------------

We’ll assume below you are installing the Djaq UI. This is not required
to provide an API but is very useful to try things out.

Install the API and UI in settings:

.. code:: python

   INSTALLED_APPS = (
       ...
       djaq.djaq_api,
       djaq.djaq_ui,
   )

Configure urls in urls.py:

.. code:: python

   urlpatterns = [
       ...
       path("dquery/", include("djaq.djaq_ui.urls")),
       path("djaq/", include("djaq.djaq_api.urls")),
   ]

You are done. You can start sending requests to:

.. code:: shell

   /djaq/api/request/

The UI will be available at:

.. code:: shell

   /dquery

Note the UI will send requests to the API endpoint so will not work
without that being configured. You send a request in this form to the
api endpoint:

.. code:: python

   {
    "queries": [
     {
      "q": "(b.id,b.name,b.pages,b.price,b.rating,b.publisher,b.alt_publisher,b.pubdate,b.in_print,) books.Book b",
      "context": {},
      "limit": "100",
      "offset": "0"
     }
    ]
   }

The UI will create this JSON for you if you want to avoid typing it.

You can also create objects, update them and delete them:

.. code:: json

   {
      "queries": [
         {
            "model": "Book",
            "output": "",
            "where": "",
            "order_by": "",
            "limit": "100",
            "offset": "0"
         }
      ]
   }


You can send multiple ``queries``, ``creates``, ``updates``, ``deletes``
operations in a single request.

Settings
--------

The API and UI will use the following settings:

-  DJAQ_WHITELIST: a list of apps/models that the user is permitted to
   include in queries.

-  DJAQ_PERMISSIONS: permissions required for staff and superuser.

-  DJAQ_VALIDATOR: if using the remote API, you can specify a validator
   class to handle all requests. The value assigned must be a class
   derived from ``djaq.query.ContextValidator``. The ``request`` object
   is always added to the context by default. You can examine this in
   the validator to make decisions like forbidding access to some users,
   etc.

In the following example, we allow the models from ‘books’ to be exposed
as well as the ``User`` model. We also require the caller to be both a
staff member and superuser:

.. code:: python

   DJAQ_WHITELIST = {
       "django.contrib.auth": ["User"],
       "books": [
           "Profile",
           "Author",
           "Consortium",
           "Publisher",
           "Book_authors",
           "Book",
           "Store_books",
           "Store",
       ],
   }
   DJAQ_PERMISSIONS = {
       "creates": True,
       "updates": True,
       "deletes": True,
       "staff": True,
       "superuser": True,
   }

If we want to allow all models for an app, we can leave away the list of
models. This will have the same effect as the setting above.

.. code:: python

   DJAQ_WHITELIST = {
       "django.contrib.auth": ["User"],
       "books": [],
   }

For permissions, you can optionally require any requesting user to be
staff and/or superuser. And you can deny or allow update operations. If
you do not provide explicit permissions for update operations, the API
will respond with 401 if one of those operations is attempted.

Custom API
----------

You can write your own custom API endpoint. Here is what a view function
for your data layer might look like with Djaq:

.. code:: python

   @login_required
   def djaq_view(request):
       data = json.loads(request.body.decode("utf-8"))
       query_string = data.get("q")
       offset = int(data.get("offset", 0))
       limit = int(data.get("limit", 0))
       context = data.get("context", {})
       return JsonResponse({
              "result": list(
                  DQ(query_string)
                  .context(context)
                  .limit(limit)
                  .offset(offset)
                  .dicts()
              )
           }
       )

You can now query any models in your entire Django deployment remotely,
provided the authentication underlying the ``login_required`` is
satisfied. This is a good solution if your endpoint is only available to
trusted clients who hold a valid authentication token or to clients
without authentication who are in your own network and over which you
have complete control. It is a bad solution on its own for any public
access since it exposes Django framework models, like users,
permissions, etc.

Most likely you want to control access in two ways:

-  Allow access to only some apps/models

-  Allow access to only some rows in each table and possibly only some
   fields.

For controlling access to models, use the whitelist parameter in
constructing the DjangoQuery:

.. code:: python

   DQ(query_string, whitelist={"books": ["Book", "Publisher",],})
     .context(context)
     .limit(limit)
     .offset(offset)
     .dicts()

This restricts access to only the ``book`` app models, Book and Publish.

You probably need a couple more things if you want to expose this to a
browser. But this gives an idea of what you can do. The caller now has
access to any authorised model resource. Serialisation is all taken care
of. Djaq comes already with a view similar to the above. You can just
start calling and retrieving any data you wish. It’s an instant API to
your application provided you trust the client or have sufficient access
control in place.

Difference between Djaq and Other Frameworks
--------------------------------------------

The core of Djaq does not actually have anything *specifically* to do
with remote requests. It is primarily a query language for Django
models. You can just as easily use it within another remote API
framework.

The default remote API for Djaq is not a REST framework. It does use
JSON for encoding data and POST to send requests. But it does not adhere
to the prescribed REST verbs. It comes with a very thin wrapper for
remote HTTP(S) requests that is a simple Django view function. It would
be trivial to write your own or use some REST framework to provide this
functionality. Mainly, it provides a way to formulate queries that are
highly expressive, compact and readable.

There is only one endpoint for Djaq on the backend.

Requests for queries, creates, updates, deletes are always POSTed.

Most importantly, the client decides what information to request using a
query language that is much more powerful than what is available from
other REST frameworks and GraphQL.

Conversely, REST frameworks and GraphQL are more useful than Djaq in
providing server-side business rule implementation.

Limitations
-----------

Djaq, without any configuration, provides access to *all* your model
data. That is usually not what you want. For instance, you would not
want to expose all user data, session data, or many other kinds of data
to even authenticated clients. It is trivial to prevent access to data
on an app or a model class level. But this might be too coarse-grained
for your application.

Djaq only supports Postgresql at this time.

Performance
-----------

You will probably experience Djaq calls as blazing fast compared to
other remote frameworks. This is because not much happens
inbetween. Once the query is parsed, it is about as fast as you will
ever get unless you do something fancy in a validator. The simplest
possible serialization is used by default.

Once the query is parsed, it is about the same overhead as calling this:

.. code:: python

   conn = connections['default']
   cursor = conn.cursor()
   self.cursor = self.connection.cursor()
   self.cursor.execute(sql)

Parsing is pretty fast and might be a negligible factor if you are
parsing during a remote call as part of a view function.

But if you want to iterate over, say, a dictionary of variables locally,
you’ll want to parse once:

.. code:: python

   dq = DQ("Book", "name").where("ilike(b.name, {namestart}")
   dq.parse()
   for vars in var_list:
       results = list(dq.context(vars).tuples())
       '<do something with results>'

Note that each call of ``context()`` causes the cursor to execute again
when ``tuples()`` is iterated.

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
     DQ("Book", """
       name,
       price as price,
       0.2 as discount,
       price * 0.2 as discount_price,
       price - (price*0.2) as diff,
       publisher.name
     """).where("b.price > 5").go()

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

   DjaqQuery(model: str | Model, columns: str | List)

The first parameter is always the model which can be the class object itself or
a string representation. The string representation can be fully qualified if
that is needed using the label of the app.

The colums can be a string with commas separating output expressions or a list
of such expressions. Use ``express as column_alias`` to provide a nicer name for
the output column.

Whitespace does not matter too much. You could put things on separate
lines.

These expressions can be Django Model fields or arithmetic expressions
or any expression supported by functions of your underlying database
that are also whitelisted by Djaq. Postgresql has thousands of
functions. About 350 of those are available in Djaq.

There where expression will filter results:

.. code::  python

   .where(condition_expression: str)

You can order by one or more valid expressions:

.. code::  python

   .order_by(column_expressions: str | List)

Prepend with minus, ``-``, to sort by descending order. 

The ``DjaqQuery()`` object is iterable:

.. code::  python

   for book in DQ("Book", "name as title, publisher.name as publisher"):
      print(f"Title: {book['title']}, Publisher: {book['publisher']}")

By default that will return `dicts``. You also have these methods that return
generators:

.. code::  python

   dq = DQ("Book", "name as title, publisher.name as publisher")
   dq.dicts()
   dq.json()
   dq.tuples()
   dq.qs()  # return a Django QuerySet

We frequently use the ``go()`` method as a quick way to dump all the results: 

.. code::  python

   In [63]: DQ("Book", "name as title, publisher.name as publisher").limit(10).go()
   Out[63]: 
   [{'title': 'Study protect relationship.', 'publisher': 'Austin-Ramos'},
   {'title': 'Prove energy various when.', 'publisher': 'Austin-Ramos'},
   {'title': 'Carry coach.', 'publisher': 'Austin-Ramos'},
   {'title': 'Increase pass newspaper.', 'publisher': 'Austin-Ramos'},
   {'title': 'Enough stuff imagine boy.', 'publisher': 'Austin-Ramos'},
   {'title': 'Impact nature back important.', 'publisher': 'Austin-Ramos'},
   {'title': 'Physical continue kitchen information.',
   'publisher': 'Austin-Ramos'},
   {'title': 'Wish quickly from tonight.', 'publisher': 'Austin-Ramos'},
   {'title': 'Upon voice similar heart capital.', 'publisher': 'Hudson Ltd'},
   {'title': 'Thank member.', 'publisher': 'Hudson Ltd'}]

The ``.qs()`` method returns a QuerySet but has some restrictions. It is exactly
what you would get form using the Django `raw()` method. One constraint is that
the result set must include the primary key.

 .. code:: python

   In [70]: list(DQ("Book", "id, name as title, publisher.name as publisher").limit(3).
      ...: qs())
   Out[70]: 
   [<Book: Station many chair pressure.>,
   <Book: Able sense quickly.>,
   <Book: That employee special notice happy.>]

Columns are automatically given names. But you can give them your own
name:

.. code:: python

   DQ("Book", "name as title, price as price, publisher.name as publisher")

or if we want to filter and get only books over 50 in price:

.. code:: python

   DQ("Book").where("price > 50")


The following filter:

.. code:: python

   DQ("Book", "b.price > 50 and ilike(Publisher.name, 'A%')")

will be translated to SQL:

::

   book.price > 50 AND publisher.name ILIKE 'A%'

The expressions are fully parsed so they are not subject to SQL injection.
Trying to do so will cause an exception. Any parameters are passed via the
parameters arguments as a dictionary to the underlying connection cursor.

Signal that you want to summarise results using an aggregate function:

.. code:: python

   DQ("Book",("publisher.name as publisher, count(b.id) as book_count").go()

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

   DQ("Book", 
   """
   name, 
   price, 
   publisher.name as publisher
   """).where("price > 50")
   order_by("name")

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

   In [35]: DQ("Book", "count(id)").go()
   Out[35]: [{'countid': 1000}]

You can qualify model names with the app label:

.. code:: python

   In [35]: DQ("book.Book", "count(id)").go()
   Out[35]: [{'countid': 1000}]

You’ll need this if you have models from different apps with the same
name.

To pass parameters, use variables in your query, like ``{myvar}``:

.. code:: python

   In [41]: oldest = '2018-12-20'
      ...: DQ("Book", "name, pubdate").where("pubdate >= {oldest}").context({"oldest": oldest}).limit(5).go
      ...: ()
   Out[41]: 
   [{'name': 'Involve something record ever father.',
   'pubdate': datetime.date(2019, 5, 8)},
   {'name': 'Item decade machine reason country.',
   'pubdate': datetime.date(2021, 12, 8)},
   {'name': 'Participant consider.', 'pubdate': datetime.date(2020, 12, 28)},
   {'name': 'Own stand single change.', 'pubdate': datetime.date(2019, 5, 9)},
   {'name': 'Almost many benefit.', 'pubdate': datetime.date(2021, 8, 29)}]




Query UI
~~~~~~~~

You can optionally install a query user interface to try out queries on
your own data set:

-  After installing djaq, add ``djaq.djaq_ui`` to INSTALLED_APPS

-  Add ``path("dquery/", include("djaq.djaq_ui.urls")),`` to
   ``urlpatterns   in the site's``\ urls.py\`

Navigate to \`/dquery/’ in your app and you should be able to try out
queries.

-  Send: call the API with the query

-  JSON: show the json that will be sent as the request data

-  SQL: show how the request will be sent to the database as sql

-  Schema: render the schema that describe the available fields

-  Whitelist: show the active whitelist. You can use this to generate a
   whilelist and edit it as required.

There is a dropdown control, ``apps``. Select the Django app. Models for
the selected app are listed below. If you click once on a model, the
result field will show the schema for that model. If you double-click
the model, it generates a query for you for all fields in that model.
Once you do that, just press “Send” to see the results.

If the query pane has the focus, you can press shift-return to send the
query request to the server.

Functions
---------

If a function is not defined by DjangoQuery, then the function name is
checked with a whitelist of functions. There are approximately 350
functions available. These are currently on supported for Postgresql and
only those will work that don’t use syntax that special to Postgresql.
Additionally, the Postgis functions are only available if you have
installed Postgis.

A user can define new functions at any time by adding to the custom
functions. Here’s an example of adding a regex matching function:

.. code:: python

   DjaqQuery.functions["REGEX"] = "{} ~ {}"

Now find all book names starting with ‘B’:

.. code:: python

   DQ("Book", "name").where("regex(name, 'B.*')").go()

We always want to use upper case for the function name when defining the
function. Usage of a function is then case-insensitive. You may wish to
make sure you are not over-writing existing functions. “REGEX” already
exists, for instance.

You can also provide a ``callable`` to ``DjaqQuery.functions``. The
callable needs to take two arguments: the function name and a list of
positional parameters and it must return SQL as a string that can either
represent a column expression or some value expression from the
underlying backend.

In the following:

.. code:: python

   DQ("Book", "name").where("like(upper(name), upper({name_search})")

``like()`` is a Djaq-defined function that is converted to
``field LIKE string``. Whereas ``upper()`` is sent to the underlying
database because it’s a common SQL function. Any function can be created
or existing functions mutated by updating the ``DjaqQuery.functions``
dict where the key is the upper case function name and the value is a
template string with ``{}`` placeholders. Arguments are positionally
interpolated.

Above, we provided this example:

.. code:: python

   DQ("Book", """
      sum(iif(b.rating < 5, b.rating, 0)) as below_5,
      sum(iif(b.rating >= 5, b.rating, 0)) as above_5
   """)

We can simplify further by creating a new function. The IIF function is
defined like this:

.. code:: python

   "CASE WHEN {} THEN {} ELSE {} END"

We can create a ``SUMIF`` function like this:

.. code:: python

   DjangoQuery.functions['SUMIF'] = "SUM(CASE WHEN {} THEN {} ELSE {} END)"

Now we can rewrite the above like this:

.. code:: python

   DQ("""(
       sumif(b.rating < 5, b.rating, 0) as below_5,
       sumif(b.rating >= 5, b.rating, 0) as above_5
       ) Book b""")

Here’s an example providing a function:

.. code:: python

   def concat(funcname, args):
       """Return args spliced by sql concat operator."""
       return " || ".join(args)

   DjangoQuery.functions['CONCAT'] = concat

Parameters and Validator
------------------------

We call the Django connection cursor approximately like this:

.. code:: python

   from django.db import connections
   cursor = connections['default']
   cursor.execute(sql, context_dict)

When we execute the resulting SQL query, named parameters are used. You
*must* name your parameters. Positional parameters are not passed:

.. code:: python

   oldest = '2000-01-01'
   DQ("Book", "id").where("pubdate >= {oldest}").context({"oldest": oldest}).tuples()

Notice that any parameterised value must be represented in the query
expression in curly braces:

::

   {myparam}

These are not f-strings! Do no use f-strings to interpolate values as this
subverts the validation against SQL injection provided by the database
connection layer.

Note what is happening here:

::

   name_search = 'Bar.*'
   DQ("Book", "name").where("regex(name, {name_search})").context(locals()).go()

To get all books starting with ‘Bar’. Or:

.. code:: python

   DQ("Book", "name").where("like(upper(name), upper({name_search})").context(request.POST)

Provided that ``request.POST`` has a ``name_search`` key/value.

You can provide a validation class that will return context variables.
The default class used is called ``ContextValidator()``. You can
override this to provide a validator that raises exceptions if data is
not valid or mutates the context data, like coercing types from ``str``
to ``int``:

.. code:: python

   class MyContextValidator(ContextValidator):
       def get(self, key, value):
           if key == 'order_no':
               return int(value)
           return value

       def context(self):
           if not 'order_no' in self.data:
               raise Exception("Need order no")
           self.super().context()

Then add the validator:

.. code:: python

   order_no = "12345"
   DQ("Order", "order_no, customer").where("order_no == {order_no}")
       .validator(MyContextValidator)
       .context(locals())
       .tuples()

You can set your own validator class in Django settings:

::

   DJAQ_VALIDATOR = MyValidator

The ``request`` parameter of the API view is added to the context and
will be available to the validator as ``request``.

Column expressions
------------------

Doing column arithmetic is supported directly in the query syntax:

.. code:: python

   DQ("Book",
      """name,
       b.price as price,
       0.2 as discount,
       price*0.2 as discount_price,
       price - (price*0.2) as diff
       """)

You can use constants:

.. code:: python

   In [60]: DQ("Book", "name, 'great read'").limit(1).go()
   Out[60]: [('Range total author impact.', 'great read')]

You can use the common operators and functions of your underlying db.

The usual arithmetic:

.. code:: python

   DQ("Book", "name, 1+1").limit(1).go()
   [{'name': 'Station many chair pressure.', '11': 2}]
   
   DQ("Book", "name, 2.0/4").limit(1).go()
   [{'name': 'Station many chair pressure.',
  '2_04': Decimal('0.50000000000000000000')}]


   DQ("Book", "2*3 as two times three").limit(1).go()
   [{'two times three': 6}]


Modulo:

.. code:: python

   DQ("Book", "mod(4.0,3)").limit(1).go()
   [{'mod4_03': Decimal('1.0')}]

Comparison as a boolean expression:

.. code:: python

   DQ("Book", "(2 > 3)").limit(1).go()
   [{'2__3': False}]

While the syntax has a superficial resemblance to Python, you do not
have access to any functions of the Python Standard Libary.

Subqueries and ``in`` clause
----------------------------

You can reference subqueries within a Djaq expression using

-  Another DjaqQuery
-  A Queryset
-  A list

The two most useful cases are using a subquery in the filter condition:

.. code:: python

   DQ("Book", "id, name").where("id in ["(id)"])

And using a subquery in the selected columns expression:

::

   DQ('(p.name, ["(count(b.id)) Book{Publisher.id == b.publisher} b"]) Publisher p')

You can use an IN clause with the keyword ``in`` (note lower case) If
you are writing queries via the Python API. Create one DjaqQuery and
reference it with ``@queryname``:

::

   DQ("Book", "id", name='dq_sub').where("name == 'B*'")
   dq = DQ("Book", "name, price").where("id in '@dq_sub'")

Note that you have to pass a name to the DjaqQuery to reference it
later. We can also use the ``data`` parameter to pass a QuerySet to the
DjangoQuery:

::

   qs = Book.objects.filter(name__startswith="B").only('id')
   dq = DQ("Book", "name, price", names={"qs_sub": qs}).where("id in '@qs_sub'")

   list(Book.objects.filter(name__startswith="B").only('id').values_list(flat=True))
   dq = DQ("Book", "name, price", names={"qs_sub": ids}).where("id in '@qs_sub'")

As with QuerySets it is nearly always faster to generate a sub query
than use an itemised list.

Order by
--------

You can order_by like this:

::

   DQ("Book", "id").where("price > 20").order_by("name")

Descending order:

::

   DQ("Book", "id").where("price > 20").order_by("-name")

You can have multple order by expressions.

::

   DQ("Book", ""name, publisher.name").where("price > 20").order_by("-name, publisher.name")

Count
-----

There are a couple ways to count results. These both return the exact
same thing:

::

   DQ("Book").count()

   DQ("Book", "count(id)").value()

Datetimes
---------

Datetimes are provided as strings in the iso format that your backend expects,
like ``"2019-01-01 18:00:00"`` or just ``"2019-01-01"`` if you don't need the time.

Constants
---------

``None``, ``True``, ``False`` are replaced in SQL with ``NULL``,
``TRUE``, ``FALSE``. All of the following work:

::

   DQ("Book", "id, name").where("in_print is True").go()
   DQ("Book", "id, name").where("in_print is not True").go()
   DQ("Book", "id, name").where("in_print is False").go()
   DQ("Book", "id, name").where("in_print == True").go()

Slicing
-------

You cannot slice a DjaqQuery. We don't cache results to keep the behaviour
explicit and obvious.

You can use ``limit()`` and ``offset()``:

::

   DjaqQuery("...").offset(1000).limit(100).tuples()

Which will provide you with the first hundred results starting from the
1000th record.

Rewind cursor
-------------

You can rewind the cursor which means just executing the SQL again:

::

   list(dq.tuples())

   # now, calling `dq.tuples()` returns nothing

   list(dq.rewind().tuples())

   # you will again see results

If you call ``DjaqQuery.context(data)``, that will effectively rewind
the cursor since an entirely new query is created and the implementation
currently doesn’t care if ``data`` is the same context as previously
supplied.

Schema
------

There is a function to get the schema available to a calling client:

.. code:: python

   from djaq.app_utils import get_schema
   print(get_schema())

Pass the same whitelist you use for exposing the query endpoint:

.. code:: python

   wl = {"books": []}
   print(get_schema(whitelist=wl))

Comparing to Django QuerySets
-----------------------------

This section is intended to highlight differences for users with good
familiarity with the ``QuerySet`` class for the purpose of understanding
capabilities and limitations of DjaqQuery.

Django provides significant options for adjusting query generation to
fit a specific use case, ``only()``, ``select_related()``,
``prefetch_related()`` are all useful for different cases. Here’s a
point-by-point comparison with Djaq:

-  ``only()``: Djaq always works in “only” mode except when you provide no
   output columns in which case it assumes all direct fields of the model but
   not foreign key relations. Only explicitly requested fields are returned.

-  ``select_related()``: The select clause only returns those columns
   explicitly defined. This feature makes loading of related fields
   non-lazy. In contrast, queries are always non-lazy in Djaq.

-  ``prefetch_related()``: When you have a m2m field as a column
   expression, the model hosting that field is repeated in results as
   many times as necessary. Another way is to use a separate query for
   the m2m related records. In anycase, ``prefetch_related()`` this is
   not relevant in Djaq.

-  F expressions: These are QuerySet workarounds for not being able to
   write expressions in the query for things like column value
   arithmetic and other expressions you want to have the db calculate.
   Djaq lets you write these directly and naturally as part of its
   syntax.

-  To aggregate with Querysets, you use ``aggregate()``, whereas Djaq
   aggregates results implicitly whenever an aggregate function appears
   in the column expressions.

-  Model instances with QuerySets exactly represent the corresponding
   Django model. Djaq’s usual return formats, like ``dicts()``,
   ``tuples()``, etc. are more akin to ``QuerySet.value_list()``.

- ``distinct()``: both ``QuerySet()`` and ``DjaqQuery()`` offer this to produce results
  that are unique for the specific output columns.

Let’s look at some direct query comparisons:

Get the average price of books:

::

   DQ("Book", "avg(price)")

compared to QuerySet:

::

   Book.objects.all().aggregate(Avg('price'))

Get the difference from the average off the maximum price for each publisher:

::

   DQ("Book", "publisher.name, max(price) - avg(price) as price_diff").go()

compared to QuerySet:

::
   from django.db.models import FloatField, Max, Avg
   Book.objects.values("publisher__name").distinct().annotate(price_diff=Max('price', output_field=FloatField()) - Avg('price', output_field=FloatField()))
   

Count books per publisher:

::

   DQ("Book", "publisher.name, count(id) as num_books").go()

compared to QuerySet:

::

   from django.db.models import Count
   Publisher.objects.annotate(num_books=Count("book"))

Count books with ratings up to and over 3:

.. code:: python

   DQ("Book", """(sum(iif(rating < 3, rating, 0)) as below_3,
       sum(iif(rating >= 3, rating, 0)) as above_3)
       """).go()

compared to QuerySet:

.. code:: python

   above_3 = Count('book', filter=Q(book__rating__gt=3))
   below_3 = Count('book', filter=Q(book__rating__lte=3))
   Publisher.objects.aggregate(below_3=below_3)
   Publisher.objects.aggregate(above_3=above_3)
   
Get average, maximum, minimum price of books:

.. code:: python

   DQ("Book", "avg(price), max(price), min(price)").go()

compared to QuerySet:

.. code:: python

   Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))


Simple counts:

``DjaqQuery.value()``: when you know the result is a single row with a
single value, you can immediately access it without further iterations:

.. code:: python

   DQ("Book", "count(id)").value()

will return a single integer value representing the count of books.

Django Subquery and OuterRef
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following do pretty much the same thing:

::

   # QuerySet
   pubs = Publisher.objects.filter(pk=OuterRef('publisher')).only('pk')
   Book.objects.filter(publisher__in=Subquery(pubs))

   # Djaq
   DQ("Book", "publisher.id", name='pubs').distinct()
   DQ("Book", "name").where("publisher in '@pubs'")

Obviously, in both cases, you would be filtering Publisher to make it
actually useful, but the effect and verbosity can be extrapolated from
the above.

There are some constraints on using subqueries like this. For instance,
the subquery cannot contain any joins.

Sample Project
--------------

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
