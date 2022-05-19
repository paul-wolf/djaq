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

from djaq import Values
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

USERNAME = "artemis"
PASSWORD = "blah"
EMAIL = "artemis@blah.com"


class TestDjaqValues(TestCase):
    def setUp(self):

        user = User.objects.create_user(username=USERNAME, email=EMAIL, password=PASSWORD)

        self.user = user
        Profile.objects.create(user=user, company="whatever")

        Author.objects.create(name="Sally", age=50)
        Author.objects.create(name="Bob", age=24)
        Author.objects.create(name="Sue", age=33)

        Publisher.objects.create(name="Simon and Bloober")
        Publisher.objects.create(name="Alternative press")
        factory.Faker("sentence", nb_words=4)
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

    def test_values(self):
        v = Values("b.id, b.name", aliases={"b": "Book"})
        self.assertEqual(v.count(), 10)

    def test_m2m(self):
        results = list(Values("b.name, b.authors.name", aliases={"b": "Book"}).dicts())
        self.assertTrue("b_name" in results[0])
        self.assertTrue("b_authors_name" in results[0])

    def test_onetoone(self):
        results = list(Values("u.username, u.email, u.profile.company", {"u": "User"}).tuples())
        self.assertTrue(results[0][0] == "artemis")

    def test_group_by(self):
        v = Values("(avg(Book.price))")
        self.assertEqual(len([t for t in v.tuples()]), 1)
        for t in v.rewind().tuples():
            self.assertTrue(isinstance(t[0], Decimal))

    def test_csv(self):
        v = Values("(b.id, b.name)", {"b": "Book"})
        for r in v.csv():
            self.assertTrue(isinstance(r, str))

    def test_json(self):
        v = Values("(Book.id, Book.name)")
        for r in v.json():
            self.assertTrue(isinstance(json.loads(r), dict))

    def test_aggregate_funcs(self):
        v = Values("(avg(b.price), max(b.price), min(b.price))", {"b": "Book"})
        for r in v.dicts():
            self.assertTrue(isinstance(r, dict))

    # @unittest.skip("we don't suppport subqueries yet")
    def test_dq_subquery_filter(self):
        """This subquery is a DjangoQuery subquery."""
        # import ipdb; ipdb.set_trace()
        len1 = len(list(Values("Book.id, Book.name").where("Book.id in ['(Book.id)']").dicts()))
        len2 = len(list(Values("(Book.id)").dicts()))
        self.assertEqual(len1, len2)

    def test_dq_subquery_select(self):
        q = """(
            p.id as id,
            p.name,
            ["(count(b.id)) books.Book{b.publisher==Publisher.id} b"] as cnt
        )
        """
        data = list(Values(q, {"p": "books.Publisher"}).dicts())
        # one entry for each publisher
        self.assertEqual(len(data), len(Publisher.objects.all()))

        # now check each individual value by getting
        # the same data with a different query
        s = """(
            count(Book.id) as cnt
        )
        """
        for rec in data:
            v = Values(s).where("Publisher.id=='$(pubid)'").context({"pubid": rec["id"]}).value()
            self.assertEqual(v, rec["cnt"])

    @unittest.skip("debug sub queries")
    def test_subquery_values(self):
        v_sub = Values("(Book.id)", name="v_sub").where("name == 'B*'")  # noqa: F841
        list(Values("Book.name, Book.price").where("id in '@v_sub'").tuples())

    @unittest.skip("debug sub queries")
    def test_subquery_queryset(self):
        qs = Book.objects.all().only("id")
        ids = [rec.id for rec in qs]
        list(Values("(b.name, b.price)", {"b": "Book"}, names={"qs_sub": ids}).where("id in '@qs_sub'").tuples())

    def test_parameter(self):
        v = Values("b.id, b.name", {"b": "Book"}).where("b.id == 1 or regex(b.name, '$(mynamepattern)')")
        list(v.context({"mynamepattern": "B.*"}).tuples())

    def test_expression_grouping(self):
        list(Values("(b.id, b.name)", {"b": "Book"}).where("(b.id == 1 or b.id == 2) and b.id == 3").tuples())

    def test_order_by(self):
        list(Values("Book.name", {"b": "Book"}).order_by("-b.name, b.publisher, -b.id").dicts())

    def test_implicit_model(self):
        v = Values("(Book.name, Book.id)")
        self.assertEquals(v.count(), 10)

    def test_custom_functions(self):
        v = Values(
            """
        (sum(iif(b.rating >= 3, b.rating, 0)) as below_3,
        sum(iif(b.rating > 3, b.rating, 0)) as above_3)
        """,
            {"b": "Book"},
        )
        list(v.tuples())

    @unittest.skip("debug sub queries")
    def test_subquery_2(self):
        pubs = Values("Publisher.id", name="pubs")  # noqa: F841
        list(Values("Book.name").where("publisher in '@pubs'").tuples())

    def test_in_list(self):
        """Test that IN (list) works."""

        # get available ids
        ids = list(Values("Book.id").tuples())
        ids = [id[0] for id in ids]

        # take just three of them
        c = {"ids": ids[:3]}
        v = Values("Book.id, Book.name").where("Book.id in '$(ids)'")
        r = list(v.context(c).dicts())

        # make sure we got three of them
        self.assertEqual(len(r), 3)

    def test_complex2(self):
        v = Values(
            """b.name,
        b.price as price,
        0.2 as discount,
        b.price * 0.2 as discount_price,
        b.price - (b.price * 0.2) as diff,
        Publisher.name as publisher
        """,
            {"b": "Book"},
        ).where("b.price > 7")

        for d in v.json():
            json.loads(d)
