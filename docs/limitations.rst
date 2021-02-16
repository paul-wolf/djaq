Limitations
===========

Compared to other frameworks like GraphQL and DRF, you can't easily
implement complex business rules on the server. This might be a deal
breaker for your application.

Djaq, without any configuration, provides access to *all* your model
data. That is usually not what you want. For instance, you would not
want to expose all user data, session data, or many other kinds of data
to even authenticated clients. It is trivial to prevent access to data
on an app or a model class level. But this might be too coarse-grained
for your application.

Djaq only supports Postgresql at this time.
