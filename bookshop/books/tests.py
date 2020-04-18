import json
import random
from decimal import Decimal

from django.test import TestCase
import factory
from faker import Faker

from djaq import DjangoQuery as DQ, DQResult

from django.db.models import Q, Avg, Count, Min, Max, Sum, FloatField, F
from books.models import Author, Publisher, Book, Store

fake = Faker()


class TestDjaq(TestCase):
    def setUp(self):

        Author.objects.create(name="Sally", age=50)
        Author.objects.create(name="Bob", age=24)
        Author.objects.create(name="Sue", age=33)

        Publisher.objects.create(name="Simon and Bloober")
        Publisher.objects.create(name="Alternative press")

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

        for i in range(3):
            store = Store.objects.create(name=fake.company())
            books = Book.objects.all().order_by("?")[:4]
            for book in books:
                store.books.add(book)
                store.save()

    def tearDown(self):
        pass

    def test_count(self):
        dq = DQ("(b.id, b.name) Book b")
        self.assertEqual(dq.count(), 10)

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

    def test_subquery(self):
        dq_sub = DQ("(b.id) Book{name == 'B*'} b", name="dq_sub")  # noqa: F841
        list(DQ("(b.name, b.price) Book{id in '@dq_sub'} b").tuples())

    def test_queryset_subquery(self):
        qs = Book.objects.filter(name__startswith="B").only("id")
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
        for t in dq.context({"mynamepattern": "B.*"}).tuples():
            pass

    def test_expression_grouping(self):
        dq = DQ("(b.id, b.name) Book{(b.id == 1 or b.id == 2) and b.id == 3} b ")
        for t in dq.tuples():
            pass

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
        for t in dq.tuples():
            pass

    def test_subquery_2(self):
        pubs = DQ("(p.id) Publisher p", name="pubs")  # noqa: F841
        list(DQ("(b.name) Book{publisher in '@pubs'} b").tuples())

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
