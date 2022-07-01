Choices
-------

If you used the ``choices`` argument defining a field in a Django model, you can use the ``_display`` suffix to get the plain text:

.. code:: python

   DQ("Book", "name, genre_display").where("price > 20").order_by("name")
   {'name': 'Whole research morning raise.', 'genre_display': 'Mystery'},
   {'name': 'Whom shake.', 'genre_display': 'Science fiction'},
   {'name': 'Woman fly land.', 'genre_display': 'Fantasy'},
   {'name': 'Wonder cup age.', 'genre_display': 'Romance'},

Instead of the ``genre`` values stored in the field.
