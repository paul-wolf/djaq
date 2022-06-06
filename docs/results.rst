Result Formats
--------------

There are serveral ways to get results from a DjangoQuery:

* ``dataframe()``: returns a pandas ``DataFrame()`` if pandas is installed
* ``dicts()``: returns a generator yielding a dict for each result row
* ``tuples()``: returns a generator yielding a tuple for each result row
* ``objs()``: returns a generator that yields a ``DQResult`` object which is basically a named tuple
* ``csv()``: returns a string that represents the entire csv document
* ``qs()``: returns Django model instances
