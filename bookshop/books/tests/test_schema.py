"""Validate DjangoSchemaProvider extraction against the bookshop models."""

import json

from django.test import SimpleTestCase

from djaq.query import schema as s
from djaq.query.schema_django import DjangoSchemaProvider, neutral_type

from books.models import Book, Publisher, Author, Store
from django.contrib.auth.models import User


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
