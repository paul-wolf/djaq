Settings
========

The API and UI will use the following settings:

* DJAQ_WHITELIST: a list of apps/models that the user is permitted to include in queries.

* DJAQ_PERMISSIONS: permissions required for staff and superuser.

* DJAQ_VALIDATOR: if using the remote API, you can specify a validator
  class to handle all requests. The value assigned must be a class
  derived from `djaq.query.ContextValidator`. The `request` object is
  always added to the context by default. You can examine this in the
  validator to make decisions like forbidding access to some users,
  etc.

In the following example, we allow the models from 'books' to be
exposed as well as the `User` model. We also require the caller to be
both a staff member and superuser:

.. code:: python

      DJAQ_WHITELIST = {
          "django.contrib.auth": ["User"],
          "books": [
          "Profile",
          "Author",
          "Consortium",
          "Publisher",
          "Book_authors",
          "Book",
          "Store_books",
          "Store",
          ],
      }
      DJAQ_PERMISSIONS = {
          "creates": True,
          "updates": True,
          "deletes": True,
          "staff": True,
          "superuser": True,
      }

If we want to allow all models for an app, we can leave away the list
of models. This will have the same effect as the setting above.

.. code:: python

    DJAQ_WHITELIST = {
        "django.contrib.auth": ["User"],
        "books": [],
    }


For permissions, you can optionally require any requesting user to be
staff and/or superuser. And you can deny or allow update
operations. If you do not provide explicit permissions for update
operations, the API will respond with 401 if one of those operations
is attempted.

