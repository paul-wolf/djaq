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
