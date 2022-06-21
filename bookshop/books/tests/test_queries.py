import random
import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime
import random
from decimal import Decimal
import unittest

from django.test import TestCase

from django.contrib.auth.models import User

import factory
from faker import Faker

from djaq import DjaqQuery as DQ
from django.db.models import Count, Q
from django.db.models import DecimalField, Avg, Max
from books.models import GENRE_CHOICES


from books.models import Author, Publisher, Book, Store, Profile

import ipdb
fake = Faker()

USERNAME = "artemis"
PASSWORD = "blah"
EMAIL = "artemis@blah.com"

def get_random_genre():
    return GENRE_CHOICES[random.randint(0, len(GENRE_CHOICES)-1)][0]

@dataclass
class BookEntity:
    id: int
    name: str
    pages: int
    price: Decimal
    rating: int
    publisher: int
    alt_publisher: int
    pubdate: datetime.date
    in_print: bool
    
class TestDjaqQuery(TestCase):
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
                genre=get_random_genre(),
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

    def test_DQ(self):
        v = DQ("Book", "id, name")
        self.assertEqual(v.count(), 10)

    def test_m2m(self):
        results = list(DQ(Book, "name, authors.name").dicts())
        self.assertTrue("name" in results[0])
        self.assertTrue("authors_name" in results[0])

    def test_onetoone(self):
        results = list(DQ("User", "username, email, profile.company").tuples())
        self.assertTrue(results[0][0] == "artemis")

    def test_rewind(self):
        v = DQ("Book", "id, publisher.name")
        assert v.go()
        assert v.rewind().go()

    def test_group_by(self):
        v = DQ(Book, "publisher.name, avg(price)")
        publisher_count = DQ("Publisher", "count(id)").value()
        assert len([t for t in v.tuples()]) == publisher_count
        for t in v.rewind().tuples():
            self.assertTrue(isinstance(t[1], Decimal))

    def test_csv(self):
        v = DQ(Book, "id, name")
        for r in v.csv():
            self.assertTrue(isinstance(r, str))

    def test_json(self):
        v = DQ(Book, "id, name")
        for r in v.json():
            self.assertTrue(isinstance(json.loads(r), dict))

    def test_aggregate_funcs(self):
        v = DQ(Book, "avg(price), max(price), min(price)")
        for r in v.dicts():
            self.assertTrue(isinstance(r, dict))

    def test_parameter(self):
        v = DQ(Book, "name").where("regex(name, {mynamepattern})")
        for name in list(v.context({"mynamepattern": "B.*"}).tuples(flat=True)):
            assert name[0] == "B"

    def test_expression_grouping(self):
        # impossible condition
        assert len(list(DQ(Book, "(id, name)").where("(id == 1 or id == 2) and id == 3").tuples())) == 0
        

    def test_order_by(self):
        assert list(DQ(Book, "name").order_by("-name, publisher, -id").dicts())

    def test_implicit_model(self):
        v = DQ(Book, "name, id")
        self.assertEquals(v.count(), 10)

    def test_custom_functions(self):
        """Also, prove we can group by all fields."""
        v = DQ(Book,
            """name,
        sumif(rating >= 3, rating, 0) as below_3,
        sumif(rating > 3, rating, 0) as above_3
        """
        )
        assert list(v.tuples())




    def test_sql(self):
        v = DQ(Book, "id, name")
        v = v.where("id in {ids}")
        assert v.sql()

    def test_complex2(self):
        discount = 0.2
        v = DQ(Book,
            """name,
        price as price,
        {discount} as discount,
        price * {discount} as discount_price,
        price - (price * {discount}) as diff,
        publisher.name as publisher
        """
        ).context({"discount": discount}).where("price > 7")

        for d in v.json():
            json.loads(d)

    def test_distinct(self):
        assert len(list(DQ(Author, "name").distinct().tuples(flat=True))) == len(set(DQ(Author, "name").tuples(flat=True)))
        
    def test_default_fields(self):
        for book in DQ("Book").dicts():
            assert len(book.keys()) 
            break
        
    def test_get(self):
        for book in DQ("Book").dicts():
            id = book["id"]
            break
        DQ(Book).get(id)
        
    def test_attribute_nesting(self):
        assert list(DQ("Book", "publisher.owner.name").dicts())
        
    
    def test_limit(self):
        #  we have 10 books
        assert len(list(DQ("Book").offset(0).limit(4).dicts())) == 4

    def test_offset(self):
        #  we have 10 books
        assert len(list(DQ("Book").offset(7).dicts())) == 3
        
        
    # test qs()
    def test_queryset(self):
        assert len(DQ("Book").qs()) == 10
        
        
    # test date operations like comparison
    def test_date_operation(self):
        DQ("Book", "pubdate").where("pubdate > '2021-01-01'").go()
    
    def test_map_dataclass(self):
        for b in DQ("Book").map(BookEntity):
            assert dataclasses.is_dataclass(b)
            break
        
    def test_map_function(self):
        def some_function(data):
            return data['name']
        for b in DQ("Book").map(some_function):
            assert isinstance(b, str)
            break
            
        
    def test_date_attributes(self):
        
        for data in DQ("Book", "pubdate").where("pubdate.year < 2022 and pubdate.year > 2020").go():
            assert data["pubdate"].year < 2022 and data["pubdate"].year > 2020 

        for data in DQ("Book", "pubdate").where("pubdate.month == 10").go():
            assert data["pubdate"].month == 10 
    
        for data in DQ("Book", "pubdate").where("pubdate.day == 2").go():
            assert data["pubdate"].day == 2 
    
    def test_update_object(self):
        # something likely to be unique
        NEW_TITLE = "my new title0854836274"
        
        def my_update_function(book, data, save=True):
            book.name = NEW_TITLE
            if save:
                book.save()
            return book
        
        for book in DQ("Book").objs():
            DQ("Book").update_object(book.id, my_update_function, dict())
            break
        
        books = DQ("Book").where("name == {title}").context({"title": NEW_TITLE}).go()
        assert books[0]["name"] == NEW_TITLE
        
    def test_reverse_relation(self):
        publishers = DQ("Publisher", "name, count(book) as num_books").go()
        assert publishers[0]["num_books"] > 0
        
    def test_in_list(self):
        """Test that IN (list) works."""

        # get available ids
        ids = list(DQ(Book, "id").tuples())
        ids = [id[0] for id in ids]

        # take just three of them
        c = {"ids": ids[:3]}
        v = DQ(Book, "id, name")        
        v = v.where("id in {ids}")
        r = list(v.context(c).dicts())
        # make sure we got three of them
        self.assertEqual(len(r), 3)

    # concatenate where clauses
        
    # test validators
    
    # test context 
    
    # test conditions()

    def test_subquery_DQ(self):
        DQ(Book, "id", name="v_sub").where("regex(name, '.*b.*')").go()   # noqa: F841
        assert len(DQ(Book, "name, price").where("id in '@v_sub'").go())

    def test_suquery_with_parameter(self):
        DQ("Book", "id", name="dq_sub").where("ilike(name, {spec})")
        DQ("Book", "name, price").where("id in '@dq_sub'").context({"spec": "B%"}).go()
    
    def test_queryset_vs_djaq(self):
        """"Get exactly equivalent queries and compare.
        There should be no difference."""
        d = DQ("Book", """publisher.id,
            sumif(rating < 3, 1, 0) as below_3,
            sumif(rating >= 3, 1, 0) as above_3
            """).order_by("publisher.id")

        below_3 = Count('book', filter=Q(book__rating__lt=3))
        above_3 = Count('book', filter=Q(book__rating__gte=3))
        q = Publisher.objects.order_by("id").annotate(below_3=below_3).annotate(above_3=above_3)
        for b in list(zip(q, d.rewind())):
            assert b[0].below_3 == b[1]["below_3"]
            
    def test_queryset_vs_djaq(self):
        d = DQ("Book", "publisher.name, max(price) - avg(price) as price_diff")

        q = Book.objects.values("publisher__name") \
            .annotate(price_diff=Max('price', output_field=DecimalField()) - Avg('price', output_field=DecimalField()))

        for b in zip(q, d.rewind()):
            assert b[0]["price_diff"] == b[1]["price_diff"]
            
    def test_in_op_boolean(self):
        assert DQ("Book").where("in_print is True").count() == DQ("Book").count()
        
        assert DQ("Book").where("in_print is not True").count() == 0
        
    def test_display_choices(self):
        for book in DQ("Book", "genre_display").dicts():
            assert book["genre_display"] in [g[1] for g in GENRE_CHOICES]