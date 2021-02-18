import json
import random
from decimal import Decimal

from django.test import TestCase
from django.test import RequestFactory
from django.test import Client
from django.db.models import Q, Avg, Count, Min, Max, Sum, FloatField, F
from django.db import connections
from django.contrib.auth.models import User

import factory
from faker import Faker

from djaq import DjangoQuery as DQ, DQResult
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


class TestDjaq(TestCase):
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

    def test_whitelist(self):

        # make sure it lets us in
        wl = {"books": ["Book"]}
        schema = get_schema(connections["default"], whitelist=wl)
        self.assertIn("books.Book", schema)
        self.assertEqual(len(schema.keys()), 1)
        DQ("(b.name) Book{ilike(b.name, 'A%')} b", whitelist=wl).parse()

        # make sure it keeps us out
        wl = {"django.contrib.auth": ["User"]}
        schema = get_schema(connections["default"], whitelist=wl)
        self.assertIn("django.contrib.auth.User", schema)
        self.assertNotIn("books.Book", schema)
        self.assertEqual(len(schema.keys()), 1)

        wl = {"django.contrib.auth": ["User"]}
        with self.assertRaises(ModelNotFoundException):
            DQ("(b.name) Book{ilike(b.name, 'A%')} b", whitelist=wl).parse()

    def test_count(self):
        dq = DQ("(b.id, b.name) Book b")
        self.assertEqual(dq.count(), 10)

    def test_m2m(self):
        results = list(DQ("(b.name, b.authors.name) Book b").dicts())
        self.assertTrue("b_name" in results[0])
        self.assertTrue("b_authors_name" in results[0])

    def test_onetoone(self):
        #  import ipdb; ipdb.set_trace()
        results = list(DQ("(u.username, u.email, u.profile.company) User u").tuples())
        self.assertTrue(results[0][0] == "artemis")

    def test_group_by(self):
        dq = DQ("(avg(b.price)) Book b")
        self.assertEqual(len([t for t in dq.tuples()]), 1)
        for t in dq.rewind().tuples():
            self.assertTrue(isinstance(t[0], Decimal))

    def test_aggregate(self):
        dq = DQ("(Publisher.name as publisher, count(b.id) as count) Book b")
        # make list of dicts
        pubs = [d for d in dq.dicts()]
        self.assertEqual(len(pubs), 2)
        self.assertTrue("publisher" in pubs[0])
        self.assertTrue("count" in pubs[0])

    def test_complex_expression(self):
        dq = DQ(
            """
        (Publisher.name, max(Book.price) -
        avg(Book.price) as price_diff) Book b
        """
        )
        for t in dq.tuples():
            pass

    def test_csv(self):
        dq = DQ("(b.id, b.name) Book b")
        for r in dq.csv():
            self.assertTrue(isinstance(r, str))

    def test_json(self):
        dq = DQ("(b.id, b.name) Book b")
        for r in dq.json():
            self.assertTrue(isinstance(json.loads(r), dict))

    def test_aggregate_funcs(self):
        dq = DQ("(avg(b.price), max(b.price), min(b.price)) Book b")
        for r in dq.dicts():
            self.assertTrue(isinstance(r, dict))

    def test_dq_subquery_filter(self):
        """This subquery is a DjangoQuery subquery."""
        # import ipdb; ipdb.set_trace()
        len1 = len(list(DQ('(b.id, b.name) Book{b.id in ["(Book.id)"]} b').dicts()))
        len2 = len(list(DQ("(Book.id)").dicts()))
        self.assertEqual(len1, len2)

    def test_dq_subquery_select(self):
        q = """(
            p.id as id,
            p.name,
            ["(count(b.id)) books.Book{b.publisher==Publisher.id} b"] as cnt
        ) books.Publisher p
        """
        data = list(DQ(q).dicts())
        # one entry for each publisher
        self.assertEqual(len(data), len(Publisher.objects.all()))

        # now check each individual value by getting
        # the same data with a different query
        s = """(
            count(b.id) as cnt
        ) books.Book{Publisher.id=='$(pubid)'} b
        """
        for rec in data:
            v = DQ(s).context({"pubid": rec["id"]}).value()
            self.assertEqual(v, rec["cnt"])

    def test_subquery_djangoquery(self):
        dq_sub = DQ("(b.id) Book{name == 'B*'} b", name="dq_sub")  # noqa: F841
        list(DQ("(b.name, b.price) Book{id in '@dq_sub'} b").tuples())

    def test_subquery_queryset(self):
        qs = Book.objects.all().only("id")
        ids = [rec.id for rec in qs]
        list(
            DQ(
                "(b.name, b.price) Book{id in '@qs_sub'} b", names={"qs_sub": ids}
            ).tuples()
        )

    def test_parameter(self):
        dq = DQ(
            """(b.id, b.name) Book{b.id == 1 or
        regex(b.name, '$(mynamepattern)')} b """
        )
        list(dq.context({"mynamepattern": "B.*"}).tuples())

    def test_expression_grouping(self):
        list(
            DQ(
                "(b.id, b.name) Book{(b.id == 1 or b.id == 2) and b.id == 3} b "
            ).tuples()
        )

    def test_order_by(self):
        list(DQ("(b.name) Book b order by (-b.name, b.publisher, -b.id)").dicts())

    def test_implicit_model(self):
        dq = DQ("(Book.name, Book.id)")
        self.assertEquals(dq.count(), 10)

    def test_custom_functions(self):
        dq = DQ(
            """
        (sum(iif(b.rating >= 3, b.rating, 0)) as below_3,
        sum(iif(b.rating > 3, b.rating, 0)) as above_3) Book b
        """
        )
        list(dq.tuples())

    def test_subquery_2(self):
        pubs = DQ("(p.id) Publisher p", name="pubs")  # noqa: F841
        list(DQ("(b.name) Book{publisher in '@pubs'} b").tuples())

    def test_in_list(self):
        """Test that IN (list) works."""

        # get available ids
        ids = list(DQ("(b.id) Book b").tuples())
        ids = [id[0] for id in ids]

        # take just three of them
        c = {"ids": ids[:3]}
        dq = DQ("(b.id, b.name) Book{b.id in '$(ids)'} b")
        r = list(dq.context(c).dicts())

        # make sure we got three of them
        self.assertEqual(len(r), 3)

    def test_function_whitelist(self):
        with self.assertRaises(UnknownFunctionException):
            list(DQ("(b.id, pg_backend_pid()) Book b").tuples())

        with self.assertRaises(UnknownFunctionException):
            list(DQ("(b.id, asdfasdfasdf()) Book b").tuples())

        # this should be fine because `ceil()` is in our whitelist
        list(DQ("(b.id, ceil(b.price)) Book b").tuples())

    def test_complex2(self):
        dq = DQ(
            """(b.name,
        b.price as price,
        0.2 as discount,
        b.price * 0.2 as discount_price,
        b.price - (b.price * 0.2) as diff,
        Publisher.name as publisher
        ) Book{b.price > 7} b"""
        )
        for d in dq.json():
            json.loads(d)

    def test_updates(self):
        SPECIAL_PRICE = 12345.01
        results = queries([{"q": "(Book.id, Book.name, Book.price)", "limit": 1}])
        book = results[0][0]
        book_id = book["book_id"]
        book_price = float(book["book_price"])
        results = updates(
            [{"_model": "books.Book", "_pk": book_id, "price": SPECIAL_PRICE}]
        )
        self.assertEqual(results[0], 1)
        c = {"special_price": SPECIAL_PRICE, "book_id": book_id}
        results = queries(
            [
                {
                    "q": "(Book.id, Book.name, Book.price) Book{id=='$(book_id)'}",
                    "limit": 1,
                    "context": c,
                }
            ]
        )
        book = results[0][0]
        book_price = book["book_price"]
        self.assertEqual(float(book_price), SPECIAL_PRICE)

    def test_deletes(self):
        #  import ipdb; ipdb.set_trace()
        book_count = DQ("(count(Book.id)) Book").value()
        book_id = DQ("(Book.id)").limit(1).value()
        data = {"_model": "books.Book", "_pk": book_id}
        deletes([data])
        book_count_new = DQ("(count(Book.id)) Book").value()
        self.assertEqual(book_count, book_count_new + 1)

    def test_remote_query(self):
        data = {
            "queries": [
                {
                    "q": "(Book.id, Book.name, Book.price, Book.pubdate)",
                    "context": {},
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
                    "_model": "books.Author",
                    "name": "joseph conrad",
                    "age": 31,
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
                    "_model": "books.Author",
                    "name": "joseph conrad",
                    "age": 31,
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
