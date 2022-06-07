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
       """).context({"discount": discount})

These expressions are evaluated in the database.

You can use literals:

.. code:: python

   In [71]: DQ("Book", "name, 'great read'").limit(1).go()
   Out[71]: [{'name': 'Station many chair pressure.', 'great_read': 'great read'}]

You can use the common operators and functions of your underlying db.

The usual arithmetic:

.. code:: python

   In [72]: DQ("Book", "name, 1+1").limit(1).go()
   Out[72]: [{'name': 'Station many chair pressure.', '11': 2}]

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

   In [121]: DQ("Book", "2 > 3 as absurd").limit(1).go()
   Out[121]: [{'absurd': False}]

While the syntax has a superficial resemblance to Python, you do not
have access to any functions of the Python Standard Libary.


