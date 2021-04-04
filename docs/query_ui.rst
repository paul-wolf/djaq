Query UI
--------

You can optionally install a query user interface to try out queries on
your own data set:

-  After installing djaq, add ``djaq.djaq_ui`` to INSTALLED_APPS

-  Add 

.. code:: python

    path("dquery/", include("djaq.djaq_ui.urls")),

to ``urlpatterns`` in the site's ``\ urls.py\``

Navigate to `/dquery/` in your app and you should be able to try out
queries.

-  Send: call the API with the query

-  JSON: show the json that will be sent as the request data

-  SQL: show how the request will be sent to the database as sql

-  Schema: render the schema that describe the available fields

-  Whitelist: show the active whitelist. You can use this to generate a
   whilelist and edit it as required.

There is a dropdown control, ``apps``. Select the Django app. Models for
the selected app are listed below. If you click once on a model, the
result field will show the schema for that model. If you double-click
the model, it generates a query for you for all fields in that model.
Once you do that, just press “Send” to see the results.

If the query pane has the focus, you can press shift-return to send the
query request to the server.

.. figure:: https://github.com/paul-wolf/djaq/blob/master/docs/images/djaq_ui.png?raw=true
   :alt: Djaq UI

