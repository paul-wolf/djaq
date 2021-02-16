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

You can set your own validator class in Django settings:

::

   DJAQ_VALIDATOR = MyValidator

The ``request`` parameter of the API view is added to the context and
will be available to the validator as ``request``.

