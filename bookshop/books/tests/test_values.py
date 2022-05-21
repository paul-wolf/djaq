import json
import random
from decimal import Decimal
import unittest

from django.test import TestCase

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

import ipdb
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
        Author.objects.create(name="Sue", age=33)

        Publisher.objects.create(name="Simon and Bloober")
        Publisher.objects.create(name="Alternative press")
        factory.Faker("sentence", nb_words=4)
        for i in range(10):
            book = Book.objects.create(
                name=fake.sentence(),
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
        v = Values("Book", "id, name")
        self.assertEqual(v.count(), 10)

    def test_m2m(self):
        results = list(Values(Book, "name, authors.name").dicts())
        self.assertTrue("name" in results[0])
        self.assertTrue("authors_name" in results[0])

    def test_onetoone(self):
        results = list(Values("User", "username, email, profile.company").tuples())
        self.assertTrue(results[0][0] == "artemis")

    def test_group_by(self):
        v = Values(Book, "avg(price)")
        self.assertEqual(len([t for t in v.tuples()]), 1)
        for t in v.rewind().tuples():
            self.assertTrue(isinstance(t[0], Decimal))

    def test_csv(self):
        v = Values(Book, "id, name")
        for r in v.csv():
            self.assertTrue(isinstance(r, str))

    def test_json(self):
        v = Values(Book, "id, name")
        for r in v.json():
            self.assertTrue(isinstance(json.loads(r), dict))

    def test_aggregate_funcs(self):
        v = Values(Book, "avg(price), max(price), min(price)")
        for r in v.dicts():
            self.assertTrue(isinstance(r, dict))

    @unittest.skip("we don't suppport subqueries yet")
    def test_dq_subquery_filter(self):
        """This subquery is a DjangoQuery subquery."""
        # import ipdb; ipdb.set_trace()
        len1 = len(list(Values(Book, "id, name").where("id in ['(id)']").dicts()))
        len2 = len(list(Values(Book, "id").dicts()))
        self.assertEqual(len1, len2)

    @unittest.skip("we don't support old syntax")
    def test_dq_subquery_select(self):
        q = """(
            id as id,
            name,
            ["(count(id)) Book{b.publisher==Publisher.id} b"] as cnt
        )
        """
        data = list(Values(Book, "Publisher", q).dicts())
        # one entry for each publisher
        self.assertEqual(len(data), len(Publisher.objects.all()))

        # now check each individual value by getting
        # the same data with a different query
        s = """(
            count(id) as cnt
        )
        """
        for rec in data:
            v = Values(Book, s).where("Publisher.id=='{pubid}'").context({"pubid": rec["id"]}).value()
            self.assertEqual(v, rec["cnt"])

    @unittest.skip("debug sub queries")
    def test_subquery_values(self):
        v_sub = Values(Book, "id", name="v_sub").where("name == 'B*'")  # noqa: F841
        list(Values(Book, "name, price").where("id in '@v_sub'").tuples())

    @unittest.skip("debug sub queries")
    def test_subquery_queryset(self):
        qs = Book.objects.all().only("id")
        ids = [rec.id for rec in qs]
        list(Values(Book, "name, price", names={"qs_sub": ids}).where("id in '@qs_sub'").tuples())

    def test_parameter(self):
        v = Values(Book, "name").where("regex(name, {mynamepattern})")
        for name in list(v.context({"mynamepattern": "B.*"}).tuples(flat=True)):
            assert name[0] == "B"

    def test_expression_grouping(self):
        list(Values(Book, "(id, name)").where("(id == 1 or id == 2) and id == 3").tuples())

    def test_order_by(self):
        list(Values(Book, "name").order_by("-name, publisher, -id").dicts())

    def test_implicit_model(self):
        v = Values(Book, "name, id")
        self.assertEquals(v.count(), 10)

    def test_custom_functions(self):
        v = Values(Book,
            """
        (sum(iif(rating >= 3, rating, 0)) as below_3,
        sum(iif(rating > 3, rating, 0)) as above_3)
        """
        )
        list(v.tuples())

    @unittest.skip("debug sub queries")
    def test_subquery_2(self):
        pubs = Values("Publisher", "id", name="pubs")  # noqa: F841
        list(Values(Book, "name").where("publisher in '@pubs'").tuples())

    def test_in_list(self):
        """Test that IN (list) works."""

        # get available ids
        ids = list(Values(Book, "id").tuples())
        ids = [id[0] for id in ids]

        # take just three of them
        c = {"ids": ids[:3]}
        v = Values(Book, "id, name")        
        v = v.where("id in {ids}")
        r = list(v.context(c).dicts())
        # make sure we got three of them
        self.assertEqual(len(r), 3)

    def test_sql(self):
        v = Values(Book, "id, name")
        v = v.where("id in {ids}")
        print(v.sql())

    def xtest_complex2(self):
        discount = 0.2
        v = Values(Book,
            """name,
        price as price,
        0.2 as discount,
        price * {discount} as discount_price,
        price - (price * 0.2) as diff,
        publisher.name as publisher
        """
        ).context({"discount": discount}).where("price > 7")

        for d in v.json():
            json.loads(d)

    def test_distinct(self):
        assert len(list(Values(Author, "name").distinct().dicts())) < len(list(Values(Author, "name").dicts()))