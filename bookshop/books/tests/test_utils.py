import json
import random
from decimal import Decimal

import unittest

from django.test import TestCase
from django.test import RequestFactory
from django.test import Client
from django.db import connections
from django.contrib.auth.models import User

import factory
from faker import Faker

from djaq import DjaqQuery as DQ
from djaq.djaq_api.views import queries, updates, creates, deletes, djaq_request_view
from djaq.app_utils import (
    model_path,
    get_db_type,
    find_model_class,
    fieldclass_from_model,
    model_field,
    field_ref,
    get_field_details,
    get_model_details,
    get_schema,
    get_model_classes,
)
from djaq.exceptions import ModelNotFoundException

from books.models import Author, Publisher, Book, Store, Profile

fake = Faker()

REQUEST_ENDPOINT = "/djaq/api/request/"
USERNAME = "artemis"
PASSWORD = "blah"
EMAIL = "artemis@blah.com"


class XTestUtils(TestCase):
    def setUp(self):

        user = User.objects.create_user(
            username=USERNAME, email=EMAIL, password=PASSWORD
        )

        self.user = user
        Profile.objects.create(user=user, company="whatever")

        Author.objects.create(name="Sally", age=50)
        Author.objects.create(name="Bob", age=24)
        Author.objects.create(name="Sue", age=33)

        Publisher.objects.create(name="Simon and Bloober")
        Publisher.objects.create(name="Alternative press")
        title = factory.Faker("sentence", nb_words=4)
        for i in range(10):
            book = Book.objects.create(
                name=factory.Faker("sentence", nb_words=4),
                pages=random.choice(range(100, 800)),
                price=random.choice(range(3, 35)),
                rating=random.choice(range(5)),
                publisher=Publisher.objects.all().order_by("?")[0],
                pubdate=fake.date_this_century(before_today=True, after_today=False),
            )
            book.authors.add(Author.objects.all().order_by("?")[0])
            book.save()

        for _ in range(3):
            store = Store.objects.create(name=fake.company())
            books = Book.objects.all().order_by("?")[:4]
            for book in books:
                store.books.add(book)
                store.save()

    def tearDown(self):
        pass

    def test_model_path(self):
        self.assertEqual(model_path(Book), "books.models.Book")

    def test_get_db_type(self):
        f = fieldclass_from_model("name", Book)
        t = get_db_type(f, connections["default"])
        self.assertEqual(t, "varchar(300)")

    def test_find_model_class(self):
        self.assertEqual(find_model_class("Book"), Book)

    def test_fieldclass_from_model(self):
        f = fieldclass_from_model("name", Book)
        self.assertEqual(f.name, "name")

    def test_model_field(self):
        m, f = model_field("Book", "name")
        self.assertEqual(f.name, "name")

    def test_field_ref(self):
        m, f = field_ref("Book.name")
        self.assertEqual(f.name, "name")

    def test_field_details(self):
        m, f = field_ref("Book.name")
        d = get_field_details(f, connections["default"])
        self.assertEqual(d["name"], "name")

    def test_get_model_details(self):
        m, f = field_ref("Book.name")
        d = get_model_details(m, connections["default"])
        self.assertEqual(d["object_name"], "Book")

    def test_get_model_classes(self):
        classes = get_model_classes()
        self.assertTrue("books.Book" in classes)

    def test_get_schema(self):
        schema = get_schema(connections["default"])
        self.assertTrue("books.Book" in schema)

