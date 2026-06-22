"""Test-support helpers for the Djaq conformance suite.

The suite is run against multiple database backends (selected with the
``DJAQ_DB`` env var, see ``bookshop/settings.py``). Some behaviours are not yet
supported on every backend because the SQL generator is still Postgres-centric.
Rather than let those show up as noisy failures, we mark them as *expected*
dialect gaps for the affected backend.

When the generator later gains support for a backend, the marked test will start
passing and ``unittest`` will report an "unexpected success", which fails the
run -- that is the signal to remove the marker. This makes the gap list a
ratchet that can only shrink.
"""

import os
import unittest

#: Normalised name of the backend the suite is currently running against.
CURRENT_DB = os.environ.get("DJAQ_DB", "postgres").lower()
if CURRENT_DB in ("sqlite", "sqlite3"):
    CURRENT_DB = "sqlite"
elif CURRENT_DB in ("postgres", "postgresql"):
    CURRENT_DB = "postgres"


def expected_dialect_gap(*backends, reason=""):
    """Mark a test as a known-unsupported dialect gap on ``backends``.

    Usage::

        @expected_dialect_gap("sqlite", reason="ILIKE is Postgres-only")
        def test_something(self):
            ...

    On the named backends the test is wrapped with ``expectedFailure`` (any
    failure or error is tolerated, and an unexpected pass fails the run). On
    every other backend the test runs normally.
    """

    def decorator(func):
        if CURRENT_DB in backends:
            return unittest.expectedFailure(func)
        return func

    return decorator
