Djaq provides a query language for Django. In contrast to the QuerySet
class that provides a Python API, Djaq queries are strings. A query
string might look like this:

::

   (b.name as title, b.publisher.name as publisher) Book b

This retrieves a list of book titles with book publisher. You can send
Djaq queries from any language, Java, Javascript, golang, etc. to a
Django application and get results as JSON.

Of course, there is a common way to do this already by using frameworks
like Django REST Framework (DRF), GraphQL, Django views, etc. The
advantage of Djaq is you can immediately provide access without writing
server side code except for security as explained below. Djaq is a good
fit if you want:

-  Microservice communication where some services don’t have access to
   the Django ORM or are not implemented with Python

-  Fast local UI development

-  Fast development of Proof of Concepts

Djaq sits on top of the Django ORM. It can happily be used alongside
QuerySets and sometimes calling a Djaq query even locally might be
preferable to constructing a Queryset, although Djaq is not a
replacement for QuerySets.

Features you might appreciate:

-  Immediate gratification with zero or minimal server-side code. There
   is minimal setup. And therefore, there is minimal wasted effort if
   you later move to another framework, like GraphQL or DRF.

-  Djaq uses a syntax that lets you compose queries using Python-like
   expressions. The query format and syntax is chosen to be written by
   hand quickly. Readability is a key goal.

-  Fast cursor semantics and explicit retrieval. It only gets data you
   asked for.

-  Obvious performance behaviour. It will trigger a query in one obvious
   way through one of the generator methods: ``.dict()``, ``.tuples()``,
   ``.json()``.

-  Complex expressions let you push computation down to the database
   layer from the client.

-  A ready-to-go CRUD API that is easy to use. You can send requests to
   have an arbitrary number of Create, Read, Write, Delete operations
   done in a single request.

-  Customisable behaviour using your own functions and data validators.

-  A handy user interface for trying out queries on your data models.

Djaq provides whitelisting of apps and models you want to expose. It
also lets you hook requests and filter to ensure only data you want to
expose is accessible.

   Note that Djaq is still in an early phase of development. No
   warranties about reliability, security or that it will work exactly
   as described.

Limitations
-----------

Compared to other frameworks like GraphQL and DRF, you can’t easily
implement complex business rules on the server. This might be a deal
breaker for your application. In that case, you should look at one of
those solutions or Plain Old Django Views.

Djaq only supports Postgresql at this time.

Values in the ``choices`` argument of fields that take only a limited
set of values will not be retrieved. Instead you get the raw field
value. These are not accessible to Djaq which only retrieves what is
available via SQL.

Quickstart
----------

You need Python 3.6 or higher and Django 2.1 or higher.

Install:

::

   pip install Djaq

The bleeding edge experience:

::

   pip install https://github.com/paul-wolf/djaq/archive/master.zip

Use:

.. code:: python

   from djaq.query import DjangoQuery as DQ

   print(list(DQ("(b.name as title, b.publisher.name as publisher) Book b").dicts()))

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
       path("dquery/", include("djaq.djaq_ui.urls")),`
       path("djaq/", include("djaq.djaq_api.urls")),`
   ]

You are done. You can start sending requests to:

::

   /djaq/api/request/

The UI will be available at:

::

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

.. code:: python

   {
      "queries": [
       {
         "q": "(b.id,b.name,b.pages,b.price,b.rating,b.publisher,b.alt_publisher,b.pubdate,b.in_print,) books.Book b",
         "context": {},
         "limit": "100",
         "offset": "0"
       }
      ],
     "creates":[{
        "_model":"Book"
        "name":"my new book",
        }],
     "updates":[{
        "_model":"Book"
        "_pk": 37,
        "name":"my new title",
        }],
     "deletes":[{
        "_model":"Book"
          "_pk": 37,
        }]
   }

You can send multiple ``queries``, ``creates``, ``updates``, ``deletes``
operations in a single request.

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
       return JsonResponse(
           {
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

Performance
-----------

Once the query is parsed, it is about the same overhead as calling this:

::

   conn = connections['default']
   cursor = conn.cursor()
   self.cursor = self.connection.cursor()
   self.cursor.execute(sql)

Parsing is pretty fast:

::

   In [12]: %timeit list(DQ("(b.name) Book{ilike(b.name, 'A%')} b").parse())
   314 µs ± 4.1 µs per loop (mean ± std. dev. of 7 runs, 1000 loops each)

and might be a negligible factor if you are parsing during a remote call
as part of a view function.

But if you want to iterate over, say, a dictionary of variables locally,
you’ll want to parse once:

.. code:: python

   dq = DQ("(b.name) Book{ilike(b.name, '$(namestart)')} b")
   dq.parse()
   for vars in var_list:
       results = list(dq.context(vars).tuples())
       <do something with results>

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

::

   (<field_exp1>, ...) <ModelName>{<filter_expression>} <alias> order by (<field_exp1>, ...)

Whitespace does not matter too much. You could put things on separate
lines:

.. code:: python

   (
      b.name, b.price,
      Publisher.name
   )
   Book{p.price > 50} b

Always start with column expressions you want to return in parens:

::

   (b.name, b.price, Publisher.name)

These expressions can be Django Model fields or arithmetic expressions
or any expression supported by functions of your underlying database.
Columns are automatically given names. But you can give them your own
name:

::

   (b.name as title, b.price as price, Publisher.name as publisher)

Next is the model alias declaration:

::

   Book b

or if we want to filter and get only books over 50 in price:

::

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

::

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
   order by b.name

Get average, minimum and maximum prices:

.. code:: python

   list(DQ("(avg(b.price) as average, min(b.price) as minimum, max(b.price) as maximum) Book b).dicts())
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

.. code:: python

   In [30]: oldest = '2018-12-20'
       ...: list(DQ("(b.name, b.pubdate) Book{b.pubdate >= '$(oldest)'} b").context({"oldest": oldest}).limit(5).tuples())
   Out[30]:
   [('Available exactly blood.', datetime.date(2018, 12, 20)),
    ('Indicate Congress none always.', datetime.date(2018, 12, 24)),
    ('Old beautiful three program.', datetime.date(2018, 12, 25)),
    ('Oil onto mission.', datetime.date(2018, 12, 21)),
    ('Key same effect me.', datetime.date(2018, 12, 23))]

Notice that the variable holder, ``$()``, *must* be in single quotes.

Query UI
~~~~~~~~

You can optionally install a query user interface to try out queries on
your own data set:

-  After installing djaq, add ``djaq.djaq_ui`` to INSTALLED_APPS

-  Add ``path("dquery/", include("djaq.djaq_ui.urls")),`` to
   ``urlpattenrs   in the sites``\ urls.py\`

Navigate to \`/dquery/’ in your app and you should be able to try out
queries.

Functions
---------

If a function is not defined by DjangoQuery, then the function name is
passed without further intervention to the underlying SQL. A user can
define new functions at any time by adding to the custom functions.
Here’s an example of adding a regex matching function:

.. code:: python

   DjangoQuery.functions["REGEX"] = "{} ~ {}"

Now find all book names starting with ‘B’:

.. code:: python

   DQ("(b.name) Book{regex(b.name, 'B.*')} b")

We always want to use upper case for the function name when defining the
function. Usage of a function is then case-insensitive. You may wish to
make sure you are not over-writing existing functions. “REGEX” already
exists, for instance.

You can also provide a ``callable`` to ``DjangoQuery.functions``. The
callable needs to take two arguments: the function name and a list of
positional parameters and it must return SQL as a string that can either
represent a column expression or some value expression from the
underlying backend.

In the following:

.. code:: python

   DQ("(b.name) Book{like(upper(b.name), upper('$(name_search)'))} b")

``like()`` is a Djaq-defined function that is converted to
``field LIKE string``. Whereas ``upper()`` is sent to the underlying
database because it’s a common SQL function. Any function can be created
or existing functions mutated by updating the ``DjangoQuery.functions``
dict where the key is the upper case function name and the value is a
template string with ``{}`` placeholders. Arguments are positionally
interpolated.

Above, we provided this example:

.. code:: python

   DQ("""(
      sum(iif(b.rating < 5, b.rating, 0)) as below_5,
      sum(iif(b.rating >= 5, b.rating, 0)) as above_5
   ) Book b""")

We can simplify further by creating a new function. The IIF function is
defined like this:

::

   "CASE WHEN {} THEN {} ELSE {} END"

We can create a ``SUMIF`` function like this:

::

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

Parameters
----------

We call the Django connection cursor approximately like this:

.. code:: python

   from django.db import connections
   cursor = connections['default']
   cursor.execute(sql, context_dict)

When we execute the resulting SQL query, named parameters are used. You
*must* name your parameters. Positional parameters are not passed:

.. code:: python

   oldest = '2000-01-01'
   DQ("(b.id) Book{b.pub_date >= '$(oldest)'} b").context({"oldest": oldest}).tuples()

Notice that any parameterised value must be represented in the query
expression in single quotes:

::

   '$(myparam)'

Therefore, when you add subqueries, their parameters have to be supplied
at the same time.

Note what is happening here:

::

   name_search = 'Bar.*'
   DQ("(b.id) Book{regex(b.name, '%(name_search)')} b").context(locals()).tuples()

To get all books starting with ‘Bar’. Or:

.. code:: python

   DQ("(b.name) Book{like(upper(b.name), upper('$(name_search)'))} b").context(request.POST)

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
   DQ("(o.order_no, o.customer) Orders{o.order_no == '%(order_no)')} b")
       .validator(MyContextValidator)
       .context(locals())
       .tuples()

Column expressions
------------------

Doing column arithmetic is supported directly in the query syntax:

.. code:: python

   DQ("""(b.name,
       b.price as price,
       0.2 as discount,
       b.price*0.2 as discount_price,
       b.price - (b.price*0.2) as diff
       ) Book b""")

You can use constants:

.. code:: python

   In [60]: list(DQ("(b.name, 'great read') Book b").limit(1).tuples())
   Out[60]: [('Range total author impact.', 'great read')]

You can use the common operators and functions of your underlying db.

The usual arithmetic:

.. code:: python

   In [36]: list(DQ("(b.name, 1+1) Book b").limit(1).tuples())
   Out[36]: [('Range total author impact.', 2)]
   In [38]: list(DQ("(b.name, 2.0/4) Book b").limit(1).tuples())
   Out[38]: [('Range total author impact.', Decimal('0.50000000000000000000'))]
   In [44]: list(DQ("(2*3) Book b").limit(1).tuples())
   Out[44]: [(6,)]

Modulo:

.. code:: python

   In [55]: list(DQ("(mod(4.0,3)) Book b").limit(1).tuples())
   Out[55]: [(Decimal('1.0'),)]

Comparison as a boolean expression:

.. code:: python

   In [45]: list(DQ("(2 > 3) Book b").limit(1).tuples())
   Out[45]: [(False,)]

While the syntax has a superficial resemblance to Python, you do not
have access to any functions of the Python Standard Libary.

Subqueries and IN clause
------------------------

You can reference subqueries within a Djaq expression using

-  Another DjangoQuery
-  A Queryset
-  A list

You can use an IN clause with the keyword ``in`` (note lower case).
Create one DjangoQuery and reference it with ``@queryname``:

::

   DQ("(b.id) Book{name == 'B*'} b", name='dq_sub')
   dq = DQ("(b.name, b.price) Book{id in '@dq_sub'} b")

Note that you have to pass a name to the DjangoQuery to reference it
later. We can also use the ``data`` parameter to pass a QuerySet to the
DjangoQuery:

::

   qs = Book.objects.filter(name__startswith="B").only('id')
   dq = DQ("(b.name, b.price) Book{id in '@qs_sub'} b", names={"qs_sub": qs})

   qs = Book.objects.filter(name__startswith="B").only('id')
   ids = [rec.id for rec in qs]
   dq = DQ("(b.name, b.price) Book{id in '@qs_sub'} b", names={"qs_sub": ids})

As with QuerySets it is nearly always faster to generate a sub query
than use an itemised list.

Django Subquery and OuterRef
----------------------------

The following do pretty much the same thing:

::

   # QuerySet
   pubs = Publisher.objects.filter(pk=OuterRef('publisher')).only('pk')
   Book.objects.filter(publisher__in=Subquery(pubs))

   # Djaq
   DQ("(p.id) Publisher p", name='pubs')
   DQ("(b.name) Book{publisher in '@pubs'} b")

Obviously, in both cases, you would be filtering Publisher to make it
actually useful, but the effect and verbosity can be extrapolated from
the above.

Order by
--------

You can order_by like this:

::

   DQ("(b.id) Book{b.price > 20} b order by (b.name)")

Descending order:

::

   DQ("(b.id) Book{b.price > 20} b order by -(b.name)")

You can use either ``+`` or ``-`` for ASC or DESC.

Count
-----

There are a couple ways to count results. These both return the exact
same thing:

::

   DQ("(Book.id)").count()

   DQ("(count(Book.id)) Book").value()

Datetimes
---------

Datetimes are provided as strings in the iso format that your backend
expects, like ‘2019-01-01 18:00:00’.

Constants
---------

``None``, ``True``, ``False`` are replaced in SQL with ``NULL``,
``TRUE``, ``FALSE``. All of the following work:

::

   DQ("(b.id, b.name) Book{in_print is True} b")
   DQ("(b.id, b.name) Book{in_print is not True} b")
   DQ("(b.id, b.name) Book{in_print is False} b")
   DQ("(b.id, b.name) Book{in_print == True} b")

Slicing
-------

You cannot slice a DjangoQuery because this would frustrate a design
goal of Djaq to provide the performance advantages of cursor-like
behaviour.

You can use ``limit()`` and ``offset()``:

::

   DjangoQuery("...").offset(1000).limit(100).tuples()

Which will provide you with the first hundred results starting from the
1000th record.

Rewind cursor
-------------

You can rewind the cursor but this is just executing the SQL again:

::

   list(dq.tuples())

   # now, calling `dq.tuples()` returns nothing

   list(dq.rewind().tuples())

   # you will again see results

If you call ``DjangoQuery.context(data)``, that will effectively rewind
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

Djaq queries can be sent over the wire as a string. That is the main
difference with Quersets. Even then, Djaq is not a replacement for
Querysets. Querysets are highly integrated with Django and have been
developed over 15 years by many developers. It is a very well thought
out framework that is the best choice working within a service based on
Django’s ORM. This section is intended to highlight differences for
users with high familiarity with the ``QuerySet`` class for the purpose
of understanding limitations and capabilities of DjangoQuery.

Django provides significant options for adjusting query generation to
fit a specific use case, ``only()``, ``select_related()``,
``prefetch_related()`` are all useful for different cases. Here’s a
point-by-point comparison with Djaq:

-  ``only()``: Djaq always works in “only” mode. Only explicitly
   requested fields are returned.

-  ``select_related()``: The select clause only returns those columns
   explicitly defined. This feature makes loading of related fields
   non-lazy. In contrast, queries are always non-lazy in Djaq.

-  ``prefetch_related()``: When you have a m2m field as a column
   expression, the model hosting that field is repeated in results as
   many times as necessary. Another way is to use a separate query for
   the m2m related records. In anycase, this is not required in Djaq.

-  F expressions: These are workarounds for not being able to write
   expressions in the query for things like column value arithmetic and
   other expressions you want to have the db calculate. Djaq lets you
   write these directly and naturally as part of its syntax.

-  To aggregate with Querysets, you use ``aggregate()``, whereas Djaq
   aggregates results whenever an aggregate function appears in the
   column expressions.

-  Model instances with QuerySets exactly represent the corresponding
   Django model. Djaq’s usual return formats, like ``dicts()``,
   ``tuples()``, etc. are more akin to ``QuerySet.value_list()``.

Let’s look at some direct query comparisons:

Get the average price of books:

::

   DQ("(avg(b.price)) Book b")

compared to QuerySet:

::

   Book.objects.all().aggregate(Avg('price'))

Get the difference off the maximum price:

::

   DQ("(Publisher.name, max(Book.price) - avg(Book.price) as price_diff) Book b")

compared to QuerySet:

::

   Book.objects.aggregate(price_diff=Max('price', output_field=FloatField()) - Avg('price'))

Count books per publisher:

::

   DQ("(Publisher.name, count(Book.id) as num_books) Book b")

compared to QuerySet:

::

   Publisher.objects.annotate(num_books=Count("book"))

Count books with ratings up to and over 5:

.. code:: python

   DQ("""(sum(iif(b.rating < 5, b.rating, 0)) as below_5,
       sum(iif(b.rating >= 5, b.rating, 0)) as above_5)
       Book b""")

compared to QuerySet:

.. code:: python

   above_5 = Count('book', filter=Q(book__rating__gt=5))
   below_5 = Count('book', filter=Q(book__rating__lte=5))
   Publisher.objects.annotate(below_5=below_5).annotate(above_5=above_5)

Get average, maximum, minimum price of books:

.. code:: python

   DQ("(avg(b.price), max(b.price), min(b.price)) Book b")

compared to QuerySet:

::

   Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))

Just as there is a ModelInstance class in Django, we have a DQResult
class:

``objs()``: return a DQResult for each result row, basically a namespace
for the object:

.. code:: python

   dq = DQ("(b.id, b.name, Publisher.name as publisher) Book b")
   for book in dq.objs():
       title = book.name
       publisher = book.publisher
       ...

Note that by default, you iterate using a generator. You cannot slice a
generator.

Some other features:

``DjangoQuery.value()``: when you know the result is a single row with a
single value, you can immediately access it without further iterations:

.. code:: python

   DQ("(count(b.id)) Book b").value()

will return a single integer value representing the count of books.

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

::

   python -m venv .venv

Activate the virtual environment:

::

   source .venv/bin/activate

The module itself does not install Django and there are no further
requirements. To install dependencies for the sample application:

::

   pip install -r requirements.txt

Now make sure there is a Postgresql instance running. The settings are
like this:

.. code:: python

   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql_psycopg2',
           'NAME': 'bookshop',
       },

So, it assumes peer authentication. Change to suite your needs. Now you
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
