"""Tests for the Djaq write side: ORM-honouring create/update/delete + transactions."""

import datetime

from django.test import TestCase

from djaq import DjaqQuery as DQ, Writer, transaction

from books.models import Book, Publisher, Author, ISBN


class TestWriter(TestCase):
    def setUp(self):
        self.pub = Publisher.objects.create(name="P")

    def _book_fields(self, **over):
        fields = {
            "name": "New Book",
            "pages": 100,
            "price": 9,
            "rating": 3,
            "publisher": self.pub,
            "pubdate": datetime.date(2021, 1, 1),
        }
        fields.update(over)
        return fields

    def test_create_returns_pk_and_honours_signals(self):
        pk = Writer().create("Book", self._book_fields())
        self.assertTrue(Book.objects.filter(pk=pk).exists())
        # the Book post_save signal (create_ISBN) must have fired -> honours ORM
        self.assertTrue(ISBN.objects.filter(book_id=pk).exists())

    def test_update_uses_instance_save(self):
        pk = Writer().create("Book", self._book_fields(name="old"))
        updated = Writer().update("Book", pk, {"name": "renamed"})
        self.assertEqual(updated, 1)
        self.assertEqual(Book.objects.get(pk=pk).name, "renamed")

    def test_update_missing_returns_zero(self):
        self.assertEqual(Writer().update("Book", 10_000_000, {"name": "x"}), 0)

    def test_delete(self):
        pk = Writer().create("Book", self._book_fields())
        self.assertEqual(Writer().delete("Book", pk), 1)
        self.assertFalse(Book.objects.filter(pk=pk).exists())
        self.assertEqual(Writer().delete("Book", pk), 0)  # already gone

    def test_get_returns_instance(self):
        a = Author.objects.create(name="Sue", age=40)
        self.assertEqual(Writer().get("Author", a.pk).name, "Sue")

    def test_transaction_is_atomic(self):
        w = Writer()
        before = Author.objects.count()
        with self.assertRaises(RuntimeError):
            with transaction():
                w.create("Author", {"name": "Temp", "age": 1})
                raise RuntimeError("boom")  # force rollback
        self.assertEqual(Author.objects.count(), before)  # the create rolled back

    def test_transaction_commits_on_success(self):
        w = Writer()
        before = Author.objects.count()
        with transaction():
            w.create("Author", {"name": "A", "age": 1})
            w.create("Author", {"name": "B", "age": 2})
        self.assertEqual(Author.objects.count(), before + 2)

    def test_reads_and_writes_are_separate(self):
        # command-query separation: the query object cannot mutate
        dq = DQ("Book")
        self.assertFalse(hasattr(dq, "get"))
        self.assertFalse(hasattr(dq, "update_object"))
