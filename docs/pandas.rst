Pandas DataFrame
----------------

Djaq will return a `pandas <https://pandas.pydata.org/>`_ DataFrame provided
that pandas is installed (``pip install pandas``):

.. code:: python

    In [1]: from djaq import DjaqQuery as DQ


    In [5]: df = DQ("Book",
    ...:     """name as Booktitle,
    ...:     price as price,
    ...:     0.2 as discount,
    ...:     price * 0.2 as discount_price,
    ...:     price - (price*0.2) as diff,
    ...:     publisher.name
    ...:    """).where("price > 5").dataframe()
    
    In [5]: df.head()
    Out[5]:
                                b_name  price  discount  discount_price  diff           publisher_name
    0           Especially week and item.   14.0       0.2             2.8  11.2             Sanchez-Tran
    1                  Than movie better.   16.0       0.2             3.2  12.8                Scott Inc
    2      Add marriage sport side above.   23.0       0.2             4.6  18.4          Patrick-Carlson
    3  Central federal knowledge any one.   18.0       0.2             3.6  14.4  Hicks, Gray and Griffin
    4                    Price size fast.   16.0       0.2             3.2  12.8          Murphy-Martinez

If pandas is not installed, an error will occur. If you are not using this feature, you do not need to install pandas. 
