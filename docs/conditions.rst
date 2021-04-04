Conditions
----------

Condition objects are like the ``Q()`` class in Django QuerySets. The class is ``B()`` for
Boolean. You can combine various expressions using the Python boolean operators:

.. code:: python

     c = (B("regex(b.name, '$(name)')") & B("b.pages > '$(pages)'")) |  B("b.rating > '$(rating)'")

You then add the condition to a DjangoQuery:

.. code:: python

    DQ('my query...').conditions(c)

If you are using variable substitution as in this example, you'll want to pass
context data. This might be from a Django request object (though it can be from
any dict-like object).

It is a special feature that if there is a ``B()`` expression that has a
variable like ``$(pages)`` and the context is missing a variable called
``pages``, that ``B()`` expression will be dropped from the final generated SQL. 

The purpose of this is to provide a filter expression that is conditional on the
presence of data on which it depends. If you have an html form with fields that
might or might not be filled by the user to filter the data, you may want to
implement a logic that says "if "name" is provided, search in the name field. If
it is not provided, the user does not want to search by name.

When you write your conditional expressions, these are what would normally go
into the filter part of the query:

.. code:: text

    (b.name as name, 
    b.price as price, 
    b.rating as rating, 
    b.pages as pages, 
    b.publisher.name as publisher) 
    Book {regex(b.name, '$(name)' and b.pages > '$(pages)' and b.rating > '$(rating)' and b.price > '$(price)'} b

In the following example, it is not required to provide data for all fields,
name, pages, rating, price. The conditional expressions will be refactored to
accommodate only those expressions that have data provided.

.. code:: python

    from djaq.conditions import B
    def book_list(request):

        c = (
            B("regex(b.name, '$(name)')")
            & B("b.pages > '$(pages)'")
            & B("b.rating > '$(rating)'")
            & B("b.price > '$(price)'")
        )

        books = list(
            DQ(
                "(b.name as name, b.price as price, b.rating as rating, b.pages as pages, b.publisher.name as publisher) Book b",
            )
            .conditions(c)           # add our conditions here
            .context(request.POST)   # add our context data here
            .limit(20)
            .dicts()
        )
        return render(request, "book_list.html", {"books": books})

You can check how your conditional expressions will look depending on the context data:

.. code:: python

    In [1]: from djaq.query import render_conditions
    In [2]: from djaq.conditions import B
    In [3]: c = B("regex(b.name, '$(name)')") & B("b.pages > '$(pages)'") & B("b.rating > '$(rating)'") & B("b.price > '$(price)'")
    In [4]: ctx = {"name": "sample", "pages": 300}
    In [5]: render_conditions(c, ctx)
    ...:
    Out[5]: "(((regex(b.name, '$(name)') and b.pages > '$(pages)')))"

