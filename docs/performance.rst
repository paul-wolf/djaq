Performance
===========

You will probably experience Djaq calls as blazing fast compared to
other remote frameworks. This is just because not much happens
inbetween. Once the query is parsed, it is about as fast as you will
ever get unless you do something fancy in a validator. The simplest
possible serialization is used by default.

Once the query is parsed, it is about the same overhead as calling this:

.. code:: python

    conn = connections['default']
    cursor = conn.cursor()
    self.cursor = self.connection.cursor()
    self.cursor.execute(sql)


Parsing is pretty fast and might be a negligible factor if you are
parsing during a remote call as part of a view function.

But if you want to iterate over, say, a dictionary of variables locally, you'll want to parse once:

.. code:: python

    dq = DQ("Book", "name").where("ilike(name, {namestart})")
    dq.parse()
    for vars in var_list:
        results = list(dq.context(vars).tuples())
        '<do something with results>'

Note that each call of `context()` causes the cursor to execute again when `tuples()` is iterated.
