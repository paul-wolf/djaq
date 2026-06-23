"""Validate DjangoSchemaProvider extraction against the bookshop models."""

import json

from django.test import SimpleTestCase, TestCase
from django.db import connections

from djaq.query import schema as s
from djaq.query import frontend
from djaq.query.resolver import Resolver
from djaq.query.generator import SQLGenerator, get_dialect
from djaq.query.schema_django import (
    DjangoSchemaProvider,
    neutral_type,
    check_drift,
    clear_schema_cache,
)
from djaq.exceptions import ModelNotFoundException

from books.models import Book, Publisher, Author, Store, Consortium
from django.contrib.auth.models import User


def generate_sql(provider, root_label, select, vendor="postgresql"):
    """Run the IR pipeline against any provider and return the SQL."""
    q = frontend.parse(None, f"({select})")
    rq = Resolver(provider, root_label).resolve(q)
    sql, _ = SQLGenerator(get_dialect(vendor)).generate(rq)
    return sql


class TestDjangoSchemaProvider(SimpleTestCase):
    def setUp(self):
        self.provider = DjangoSchemaProvider()
        self.book = self.provider.entity(Book)

    def test_entity_basics(self):
        self.assertEqual(self.book.key, "books.Book")
        self.assertEqual(self.book.name, "Book")
        self.assertEqual(self.book.table, "books_book")
        self.assertEqual(self.book.pk, "id")

    def test_neutral_types(self):
        self.assertEqual(self.book.field("pubdate").type, "date")
        self.assertEqual(self.book.field("price").type, "decimal")
        self.assertEqual(self.book.field("name").type, "string")
        self.assertEqual(self.book.field("pages").type, "int")
        self.assertEqual(self.book.field("in_print").type, "bool")
        # raw fallback for anything unmapped
        self.assertEqual(neutral_type("WeirdCustomField"), "weirdcustom")

    def test_choices_captured(self):
        genre = self.book.field("genre")
        self.assertEqual(genre.type, "string")
        self.assertIn(("O", "Other"), genre.choices)

    def test_fk_is_both_field_and_relation(self):
        # publisher appears as a column field (publisher_id) ...
        self.assertEqual(self.book.field("publisher").column, "publisher_id")
        # ... and as a traversable relation
        rel = self.book.relation("publisher")
        self.assertEqual(rel.kind, "fk")
        self.assertEqual(rel.target, "books.Publisher")
        self.assertEqual(rel.keys[0], s.JoinKey("books_book", "publisher_id", "books_publisher", "id"))

    def test_m2m_relation(self):
        rel = self.book.relation("authors")
        self.assertEqual(rel.kind, "m2m")
        self.assertEqual(rel.target, "books.Author")
        self.assertEqual(rel.link_table, "books_book_authors")
        self.assertEqual(
            rel.link_keys[0],
            s.JoinKey("books_book_authors", "book_id", "books_book", "id"),
        )
        self.assertEqual(
            rel.keys[0],
            s.JoinKey("books_author", "id", "books_book_authors", "author_id"),
        )

    def test_reverse_relation(self):
        pub = self.provider.entity(Publisher)
        rel = pub.relation("book")
        self.assertEqual(rel.kind, "reverse")
        self.assertEqual(rel.target, "books.Book")
        self.assertEqual(rel.keys[0], s.JoinKey("books_publisher", "id", "books_book", "publisher_id"))

    def test_reverse_o2o_relation(self):
        user = self.provider.entity(User)
        rel = user.relation("profile")
        self.assertEqual(rel.kind, "reverse")
        self.assertEqual(rel.target, "books.Profile")

    def test_schema_from_and_roundtrip(self):
        schema = self.provider.schema_from([Book, Publisher, Author, Store])
        self.assertEqual(schema.get("Book").key, "books.Book")  # lookup by short name
        # full JSON round-trip is lossless
        restored = s.Schema.from_dict(json.loads(json.dumps(schema.to_dict())))
        self.assertEqual(restored.to_dict(), schema.to_dict())

    def test_django_optional_generation(self):
        """A JSON-reloaded schema drives the pipeline identically -- no Django."""
        schema = self.provider.schema_from([Book, Publisher, Author])
        reloaded = s.Schema.from_json(schema.to_json())
        select = "name, publisher.name, authors.name"
        sql_from_json = generate_sql(reloaded, "books.Book", select)
        sql_from_django = generate_sql(DjangoSchemaProvider(), "books.Book", select)
        self.assertEqual(sql_from_json, sql_from_django)
        self.assertIn("books_publisher", sql_from_json)
        self.assertIn("books_book_authors", sql_from_json)

    def test_schema_is_access_boundary(self):
        """Resolution can only reach entities in the schema -- the scope IS the whitelist."""
        scoped = self.provider.schema_from([Book])  # Publisher deliberately excluded
        # selecting a local column is fine
        generate_sql(scoped, "books.Book", "name")
        # but traversing to an out-of-scope entity is refused at resolution time
        with self.assertRaises(ModelNotFoundException):
            generate_sql(scoped, "books.Book", "publisher.name")


class TestSchemaScoping(SimpleTestCase):
    """A scoped schema is the authorization surface (entity + field level)."""

    def setUp(self):
        self.full = DjangoSchemaProvider().schema_from([Book, Publisher, Author])

    def test_scope_limits_fields_and_entities(self):
        scoped = self.full.scope({"books.Book": ["name", "price"]})
        self.assertEqual(set(scoped.get("books.Book").fields), {"name", "price"})
        self.assertIsNone(scoped.get("books.Publisher"))  # entity out of scope
        # relations are retained; traversal just fails at get_entity later
        self.assertIsNotNone(scoped.get("books.Book").relation("publisher"))

    def test_field_level_authorization_via_resolver(self):
        scoped = self.full.scope({"books.Book": ["name"]})
        # an allowed field resolves
        generate_sql(scoped, "books.Book", "name")
        # a hidden field cannot be named
        with self.assertRaises(Exception):
            generate_sql(scoped, "books.Book", "price")

    def test_entity_level_authorization_via_resolver(self):
        scoped = self.full.scope({"books.Book": "*"})  # Publisher excluded
        with self.assertRaises(ModelNotFoundException):
            generate_sql(scoped, "books.Book", "publisher.name")

    def test_djaqquery_accepts_scoped_provider(self):
        from djaq import DjaqQuery as DQ

        scoped = self.full.scope({"books.Book": ["name", "price"]})
        # allowed field -> SQL builds
        self.assertIn("name", DQ("Book", "name", provider=scoped).sql())
        # hidden field -> refused at construction
        with self.assertRaises(Exception):
            DQ("Book", "rating", provider=scoped).sql()
        # default fields come from the scope, not all of Django's
        default_sql = DQ("Book", provider=scoped).sql()
        self.assertIn("name", default_sql)
        self.assertNotIn("rating", default_sql)


class TestSchemaCache(SimpleTestCase):
    """The process-wide entity cache amortises extraction without bypassing auth."""

    def test_extraction_is_cached_across_providers(self):
        clear_schema_cache()
        first = DjangoSchemaProvider().get_entity("books.Book")
        # a fresh provider reuses the cached Entity object (no re-extraction)
        second = DjangoSchemaProvider().get_entity("books.Book")
        self.assertIs(first, second)
        # clearing forces re-extraction
        clear_schema_cache()
        self.assertIsNot(first, DjangoSchemaProvider().get_entity("books.Book"))

    def test_cache_does_not_bypass_whitelist(self):
        # prime the cache with no whitelist
        DjangoSchemaProvider().get_entity("books.Publisher")
        # a whitelist excluding Publisher must still be enforced despite the cache
        with self.assertRaises(ModelNotFoundException):
            DjangoSchemaProvider(whitelist={"books": ["Book"]}).get_entity(
                "books.Publisher"
            )


class TestSchemaDrift(TestCase):
    """Drift detection needs a real database, so this uses TestCase (test DB)."""

    def test_extracted_schema_has_no_drift(self):
        provider = DjangoSchemaProvider()
        schema = provider.schema_from([Book, Publisher, Author, Consortium, Store])
        self.assertEqual(check_drift(schema, connections["default"]), [])

    def test_drift_is_reported(self):
        provider = DjangoSchemaProvider()
        schema = provider.schema_from([Book])
        # a phantom column on a real table, and a phantom entity/table
        schema.get("books.Book").fields["ghost"] = s.Field("ghost", "ghost_col", "string")
        schema.add(s.Entity("x.Ghost", "Ghost", "ghost_table", "id"))
        problems = check_drift(schema, connections["default"])
        self.assertTrue(any("ghost_col" in p for p in problems))
        self.assertTrue(any("ghost_table" in p for p in problems))
