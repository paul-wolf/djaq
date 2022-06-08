import json
import random
from decimal import Decimal

import unittest

from django.test import TestCase
from django.test import RequestFactory
from django.test import Client
from django.db.models import Q, Avg, Count, Min, Max, Sum, FloatField, F
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
from djaq.exceptions import ModelNotFoundException, UnknownFunctionException

from books.models import Author, Publisher, Book, Store, Profile

fake = Faker()

REQUEST_ENDPOINT = "/djaq/api/request/"
USERNAME = "artemis"
PASSWORD = "blah"
EMAIL = "artemis@blah.com"



class TestDjaqAPI(TestCase):
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


    def test_whitelist(self):

        # make sure it lets us in
        wl = {"books": ["Book"]}
        schema = get_schema(connections["default"], whitelist=wl)
        self.assertIn("books.Book", schema)
        self.assertEqual(len(schema.keys()), 1)
        
        DQ("Book", "name", whitelist=wl).where("ilike(name, 'A%')").construct()

        # make sure it keeps us out
        wl = {"django.contrib.auth": ["User"]}
        schema = get_schema(connections["default"], whitelist=wl)
        self.assertIn("django.contrib.auth.User", schema)
        self.assertNotIn("books.Book", schema)
        self.assertEqual(len(schema.keys()), 1)

        wl = {"django.contrib.auth": ["User"]}
        with self.assertRaises(ModelNotFoundException):
            DQ("Book", "name", whitelist=wl).where("ilike(name, 'A%')").construct()

        #  it also needs to refuse related models
        wl = {"books": ["Book"]}
        with self.assertRaises(ModelNotFoundException):
            DQ("Book", "publisher.name", whitelist=wl).where("ilike(name, 'A%')").construct()


    def test_updates(self):
        SPECIAL_PRICE = 12345.01
        results = queries({
            "queries": [
                {
                    "model": "Book",
                    "output": "id, name, price, pubdate",
                    "limit": "1",
                    "offset": "0",
                }
            ]
        })
        book = results[0][0]
        book_id = book["id"]
        book_price = float(book["price"])
        results = updates(
            [{"model": "books.Book", "pk": book_id, "fields":{"price": SPECIAL_PRICE}}]
        )
        self.assertEqual(results[0], 1)
        c = {"special_price": SPECIAL_PRICE, "book_id": book_id}
        results = queries(
            {"queries": [
                {
                    "model": "Book",
                    "output": "id, name, price",
                    "where": f"id=={book_id}",
                    "limit": 1,
                    "context": c,
                }
            ]}
        )
        book = results[0][0]
        book_price = book["price"]
        self.assertEqual(float(book_price), SPECIAL_PRICE)

    def test_deletes(self):
        #  import ipdb; ipdb.set_trace()
        book_count = DQ("Book", "count(id)").value()
        book_id = DQ("Book", "id").limit(1).value()
        data = {"model": "books.Book", "pk": book_id}
        deletes([data])
        book_count_new = DQ("Book", "count(id)").value()
        self.assertEqual(book_count, book_count_new + 1)

    def test_remote_query(self):
        data = {
            "queries": [
                {
                    "model": "Book",
                    "output": "(id, name, price, pubdate)",
                    "limit": "100",
                    "offset": "0",
                }
            ]
        }
        request_factory = RequestFactory()
        request = request_factory.post(
            REQUEST_ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        request.user = self.user
        response = djaq_request_view(request)
        r = json.loads(response.content.decode())
        self.assertTrue("result" in r)

        result = r.get("result")
        self.assertTrue("queries" in result)
        self.assertTrue("creates" in result)
        self.assertTrue("updates" in result)
        self.assertTrue("deletes" in result)

        self.assertEqual(len(result.get("queries")[0]), 10)

    def test_remote_create(self):
        data = {
            "creates": [
                {
                    "model": "books.Author",
                    "fields": {
                        "name": "joseph conrad",
                        "age": 31,
                    }
                }
            ]
        }

        c = Client()
        r = c.login(username=USERNAME, password=PASSWORD)

        r = c.post(REQUEST_ENDPOINT, data, content_type="application/json")
        result = json.loads(r.content.decode())["result"]
        self.assertTrue("queries" in result)
        self.assertTrue("creates" in result)
        self.assertTrue("updates" in result)
        self.assertTrue("deletes" in result)

        pk = result.get("creates")[0]
        a = Author.objects.get(name="joseph conrad")
        self.assertEquals(pk, a.id)

    def test_remote_update(self):
        data = {
            "creates": [
                {
                    "model": "books.Author",
                    "fields": {
                        "name": "joseph conrad",
                        "age": 31,
                    }
                }
            ]
        }

        c = Client()
        r = c.login(username=USERNAME, password=PASSWORD)

        r = c.post(REQUEST_ENDPOINT, data, content_type="application/json")
        result = json.loads(r.content.decode())["result"]
        self.assertTrue("queries" in result)
        self.assertTrue("creates" in result)
        self.assertTrue("updates" in result)
        self.assertTrue("deletes" in result)

        pk = result.get("creates")[0]
        a = Author.objects.get(name="joseph conrad")
        self.assertEquals(pk, a.id)
