"""Guards that the parse->resolve->generate pipeline stays Django-free.

Two complementary checks:

* structural -- the pure modules import nothing from ``django``;
* functional -- in a fresh interpreter with Django installed but NOT configured
  (no settings), a JSON schema still drives full SQL generation.
"""

import ast
import inspect
import os
import subprocess
import sys
import unittest
from pathlib import Path

from djaq.query import ir, schema, frontend, resolver, sql_functions
from djaq.query.generator import (
    base as gen_base,
    sqlite as gen_sqlite,
    postgres as gen_pg,
    mysql as gen_mysql,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

PURE_MODULES = [
    ir,
    schema,
    frontend,
    resolver,
    sql_functions,
    gen_base,
    gen_sqlite,
    gen_pg,
    gen_mysql,
]


def _imported_modules(module):
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


class TestPipelineIsDjangoFree(unittest.TestCase):
    def test_pure_modules_import_no_django(self):
        for module in PURE_MODULES:
            django = [
                n
                for n in _imported_modules(module)
                if n == "django" or n.startswith("django.")
            ]
            self.assertEqual(
                django, [], f"{module.__name__} imports Django: {django}"
            )


# A schema authored as plain JSON -- no Django involved in producing it here.
SCHEMA_JSON = """
{"entities": {
  "app.Book": {"name": "Book", "table": "book", "pk": "id",
    "fields": {"name": {"column": "name", "type": "string", "choices": []},
               "publisher": {"column": "publisher_id", "type": "int", "choices": []}},
    "relations": {"publisher": {"kind": "fk", "target": "app.Publisher",
        "keys": [{"left_table": "book", "left_column": "publisher_id",
                  "right_table": "publisher", "right_column": "id"}],
        "link_table": null, "link_keys": []}}},
  "app.Publisher": {"name": "Publisher", "table": "publisher", "pk": "id",
    "fields": {"name": {"column": "name", "type": "string", "choices": []}},
    "relations": {}}
}}
"""

_SUBPROCESS = """
import sys
from django.conf import settings
assert not settings.configured, "Django settings must NOT be configured"

from djaq.query.schema import Schema
from djaq.query import frontend
from djaq.query.resolver import Resolver
from djaq.query.generator import SQLGenerator, get_dialect

schema = Schema.from_json(sys.stdin.read())
q = frontend.parse(None, "(name, publisher.name as pub)")
rq = Resolver(schema, "app.Book").resolve(q)
sql, _ = SQLGenerator(get_dialect("sqlite")).generate(rq)
print("SQL>>>" + sql)
"""


class TestRunsWithoutDjangoSettings(unittest.TestCase):
    def test_generate_sql_with_unconfigured_django(self):
        env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
        result = subprocess.run(
            [sys.executable, "-c", _SUBPROCESS],
            input=SCHEMA_JSON,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SQL>>>SELECT "book"."name", "publisher"."name"', result.stdout)
        self.assertIn("LEFT JOIN publisher", result.stdout)


if __name__ == "__main__":
    unittest.main()
