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