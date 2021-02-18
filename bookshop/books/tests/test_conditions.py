from django.test import TestCase

from djaq.conditions import B
from djaq.query import render_conditions


class TestConditions(TestCase):
    def setUp(self):
        pass

    def test_booleans(self):
        a = B("book.id == 1")
        b = B("publisher.id != '$(pub_id)'")
        c = B("book.publish_date > today")
        n = a & (b | c)
        condition_string = render_conditions(n, {"pub_id": 1})
        assert "book.id" in condition_string
