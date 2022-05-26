Column expressions
------------------

Doing column arithmetic is supported directly in the query syntax:

.. code:: python

   discount = 0.2
   DQ("Book", """name,
       price as price,
       {discount} as discount,
       price * {discount} as discount_price,
       price - (price * {discount}) as diff
       """)

You can use literals:

.. code:: python

   In [60]: list(DQ("Book", "name, 'great read'").limit(1).tuples())
   Out[60]: [('Range total author impact.', 'great read')]

You can use the common operators and functions of your underlying db.

The usual arithmetic:

.. code:: python

   In [36]: list(DQ("Book", "name, 1+1").limit(1).tuples())
   Out[36]: [('Range total author impact.', 2)]
   In [38]: list(DQ("Book", "name, 2.0/4").limit(1).tuples())
   Out[38]: [('Range total author impact.', Decimal('0.50000000000000000000'))]
   In [44]: list(DQ("Book", "2*3").limit(1).tuples())
   Out[44]: [(6,)]

Modulo:

.. code:: python

   In [55]: list(DQ("Book", "mod(4.0,3)").limit(1).tuples())
   Out[55]: [(Decimal('1.0'),)]

Comparison as a boolean expression:

.. code:: python

   In [45]: list(DQ("Book", "2 > 3").limit(1).tuples())
   Out[45]: [(False,)]

While the syntax has a superficial resemblance to Python, you do not
have access to any functions of the Python Standard Libary.
