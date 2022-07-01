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


    def test_booleans1(self):
        a = B("a")
        b = B("b")
        c = B("c")
        
        assert str(b & c | a) == '((b and c) or a)'
        
        assert str(b | (c & a & c)) == '(b or ((c and a) and c))'