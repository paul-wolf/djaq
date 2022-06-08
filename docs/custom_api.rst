Remote API
==========

If you install the djaq_api app in INSTALLED_APPS, you have a remote api installed. 

You POST requests to the endpoint, which by default is ``/djaq/api/request/``

All requests have this overall structure:

.. code:: python

    {
        "queries": [],
        "updates": [],
        "deletes": [],
        "creates": []
    }

Any section can be left away.

Remote Queries
--------------

Provide at least ``model`` as an argument:

.. code:: python

    {
        "queries": [
            {
                "model": "Book",
                "output": "id, name, price",
                "where": "id==3",
                "limit": 1,
            } 
        ]
    }

This will provide id, name, price for a Book with id of 3. 

Remote Updates
--------------

Provide ``model`` and ``pk`` as arguments and then a set of field name/values:


.. code:: python

    {
        "updates": [
            {
                "model": "books.Book", 
                "pk": 3,
                "fields": {
                    "price": 3.99
                }
            }
        ]
    }

Remote Creates
--------------

.. code:: python

    {
        "creates": [
            {
                "model": "books.Book", 
                "fields": {
                    "name": "My great american novel",
                    "publisher_id": 10,
                    "price": 3.99
                }
            }
        ]
    }

Remote Deletes
--------------

Specify the model and primary key:

.. code:: python

    {
        "updates": [
            {
                "model": "books.Book", 
                "pk": 3,
            }
        ]
    }

Custom API
----------

You can write your own custom API endpoint. Here is what a view function
for your data layer might look like with Djaq:

.. code:: python

    @login_required
    def djaq_view(request):
        data = json.loads(request.body.decode("utf-8"))
        model_name = data.get("model")
        output_expressions = data.get("where")
        order_by = data.get("order_by")
        offset = int(data.get("offset", 0) or 0)
        limit = int(data.get("limit", 0) or 0)
        context = data.get("context", dict() or dict())
        return JsonResponse({
            "result": list(
                DQ(model_name, output_expressions)
                .where(where)
                .order_by(order_by)
                .context(context)
                .limit(limit)
                .offset(offset)
                .dicts()
            )
            }
        )


You can now query any models in your entire Django deployment
remotely, provided the authentication underlying the `login_required`
is satisfied. This is a good solution if your endpoint is only
available to trusted clients who hold a valid authentication token or
to clients without authentication who are in your own network and over
which you have complete control. It is a bad solution on its own for
any public access since it exposes Django framework models, like
users, permissions, etc.

Most likely you want to control access in two ways:

* Allow access to only some apps/models

* Allow access to only some rows in each table and possibly only some fields.

For controlling access to models, use the whitelist parameter in constructing the DjangoQuery:

.. code:: python

    DQ(model_name, column_expressions, whitelist={"books": ["Book", "Publisher",],}) \
        .context(context) \
        .limit(limit) \
        .offset(offset) \
        .dicts()

This restricts access to only the `book` app models, Book and Publish.

You probably need a couple more things if you want to expose this to a
browser. But this gives an idea of what you can do. The caller now has
access to any authorised model resource. Serialisation is all taken
care of. Djaq comes already with a view similar to the above. You can
just start calling and retrieving any data you wish. It's an instant
API to your application provided you trust the client or have
sufficient access control in place.