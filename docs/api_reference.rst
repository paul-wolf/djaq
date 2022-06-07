API Reference
=============


.. code:: python

    DjaqQuery(
            model_source: Union[models.Model, str],
            select_source: Union[str, List, None] = None,
            name: str = None,
            whitelist=None,
        )

Construct a DjaqQuery object. 

- model_source: the Django model as a string, optionally with label qualifier or a Model class. 
- select_source: the output column expressions that may be aliased to a name
  with ``.. as my_name``. This argument can be a string that separates the
  output columns with columns or a ``list`` with a column definition per
  element.
- name: provide a name for the query for use later in subqueries
- whitelist: provide a list of models to allow 


context(context: Dict) -> DjaqQuery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- context: a dict that contains parameter names and values. 


conditions(node: B) -> DjaqQuery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- node: an objects of class ``B()`` that encapsulates a filter condition which can be a complex, nested object.



count() -> int 
~~~~~~~~~~~~~~

Count the result set. 

csv()
~~~~~

Return a generator that returns a comma separated value representation of the result set.

get(pk_value: any) -> Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Return a Django model instance whose primary key is ``pk_value``.

go()
~~~~

A shortcut for ``list(dq.dicts())``.


distinct()
~~~~~~~~~~

Make results unique.

dicts()
~~~~~~~

Return a generator that returns dictionary representations of the result set.

json()
~~~~~~

Return a generator that returns JSON representations of the result set.

limit(limit: int) -> DjaqQuery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Restrict the results to ``limit`` items.

objs()
~~~~~~

Return a generator that returns objects of type ``DQResult`` that are essentially named tuples of the result set. 

offset(offset: int) -> DjaqQuery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start the results at ``offset`` of the filtered result set.

map(result_type: Union[callable, dataclasses.dataclass], data=None)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Return a generator that produces a result of a type specified by the dataclass
of ``result_type`` or returns the type returned by the callable. 

When using a dataclass, Djaq will try to map field names of the results to the
dataclass field names. The names must be exact matches. Use ``... as my_name``
in your column definitions to get these match up.

When using a callable, your functional or other callable will receive a dict
representation of the result set and you can return whatever you wish.

- result_type: a callable or dataclass
- data: the context dict for the query

order_by() -> DjaqQuery
~~~~~~~~~~~~~~~~~~~~~~~

qs() -> QuerySet
~~~~~~~~~~~~~~~~

Return a Django ``QuerySet`` class with the filtered results. This QuerySet is exact what you get from ``QuerySet.raw()``

rewind() -> DjaqQuery
~~~~~~~~~~~~~~~~~~~~~

This will reset the cursor if you have already started to iterate the results with one of the generator methods.

schema -> Dict
~~~~~~~~~~~~~~

A property that returns a dict representing the schema of a model. Use like this: 

.. code:: python

    DQ("Book").schema


schema_all(connection=None) -> Dict
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A class method that return a dict of the schema for all models.

.. code:: python

    DQ.schema_all()

You can pass it the connection name optionally. 

sql() -> str
~~~~~~~~~~~~

Return the SQL for the DjaqQuery.

tuples()
~~~~~~~~

Return a generator that returns objects of type ``Tuple`` for the result set.

update_object(pk_value: any, update_function: callable, data: Dict, save=True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This will update the object whose primary key is ``pk_value`` by calling
``update_function()``, returning whatever the return value is of that callable.

value()
~~~~~~~

Return the first field of the first record of the result set. This mainly only makes sense when aggregating. 


where(node: Union[str, B]) -> DjaqQuery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Define a filter condition for the query. 
