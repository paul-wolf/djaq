Difference between Djaq and Other Frameworks
============================================

The core of Djaq does not actually have anything *specifically* to do
with remote requests. It is primarily a query language for Django
models. You can just as easily use it within another remote API
framework.

The default remote API for Djaq is not a REST framework. It does use
JSON for encoding data and POST to send requests. But it does not
adhere to the prescribed REST verbs. It comes with a very thin wrapper
for remote HTTP(S) requests that is a simple Django view function. It
would be trivial to write your own or use some REST framework to
provide this functionality. Mainly, it provides a way to formulate
queries that are highly expressive, compact and readable.

There is only one endpoint for Djaq on the backend.

Requests for queries, creates, updates, deletes are always POSTed.

Most importantly, the client decides what information to request using
a query language that is much more powerful than what is available
from other REST frameworks and GraphQL.

Conversely, REST frameworks and GraphQL are more useful than Djaq in
providing server-side business rule implementation.