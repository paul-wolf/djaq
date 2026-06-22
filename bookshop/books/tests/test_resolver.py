"""Unit tests for the resolver: IR Name -> FieldRef + join graph.

Resolution only reads model metadata, so no database rows are required.
"""

from django.test import SimpleTestCase

from djaq.query import ir
from djaq.query.resolver import Resolver
from djaq.query.schema import JoinKey
from djaq.query.schema_django import DjangoSchemaProvider
from djaq.exceptions import UnknownFunctionException

from books.models import Book, Publisher


def resolver_for(model):
    return Resolver(DjangoSchemaProvider(), model._meta.label)


def ir_jk(lt, lc, rt, rc):
    return JoinKey(lt, lc, rt, rc)


class TestResolver(SimpleTestCase):
    def resolve_path(self, model, path):
        r = resolver_for(model)
        expr = r.resolve_path(path)
        return r, expr

    def test_standalone_field(self):
        r, expr = self.resolve_path(Book, ("name",))
        self.assertIsInstance(expr, ir.FieldRef)
        self.assertEqual(expr.column, "name")
        self.assertEqual(expr.relation.entity.name, "Book")
        self.assertEqual(len(r.relations), 1)

    def test_fk_path_adds_join(self):
        r, expr = self.resolve_path(Book, ("publisher", "name"))
        self.assertIsInstance(expr, ir.FieldRef)
        self.assertEqual(expr.column, "name")
        self.assertEqual(expr.relation.entity.name, "Publisher")
        # Book (root) + Publisher
        self.assertEqual([rel.entity.name for rel in r.relations], ["Book", "Publisher"])
        pub = r.relations[1]
        self.assertEqual(
            pub.join_keys[0], ir_jk("books_book", "publisher_id", "books_publisher", "id")
        )

    def test_nested_fk_path(self):
        r, expr = self.resolve_path(Book, ("publisher", "owner", "name"))
        self.assertIsInstance(expr, ir.FieldRef)
        self.assertEqual(expr.column, "name")
        self.assertEqual(len(r.relations), 3)  # Book, Publisher, Consortium

    def test_m2m_path_inserts_link_table(self):
        r, expr = self.resolve_path(Book, ("authors", "name"))
        self.assertIsInstance(expr, ir.FieldRef)
        self.assertEqual(expr.column, "name")
        # Book + link table + Author
        self.assertEqual(len(r.relations), 3)
        self.assertIsNone(r.relations[1].entity)  # the link table has no entity

    def test_date_attribute(self):
        r, expr = self.resolve_path(Book, ("pubdate", "year"))
        self.assertIsInstance(expr, ir.DateExtract)
        self.assertEqual(expr.part, "year")
        self.assertIsInstance(expr.source, ir.FieldRef)
        self.assertEqual(expr.source.column, "pubdate")

    def test_display_choices_becomes_case(self):
        r, expr = self.resolve_path(Book, ("genre_display",))
        self.assertIsInstance(expr, ir.Case)
        self.assertTrue(len(expr.whens) > 0)
        cond, result = expr.whens[0]
        self.assertIsInstance(cond, ir.BinaryOp)
        self.assertEqual(cond.op, ir.Op.EQ)

    def test_reverse_relation(self):
        r, expr = self.resolve_path(Publisher, ("book",))
        self.assertIsInstance(expr, ir.FieldRef)
        self.assertEqual([rel.entity.name for rel in r.relations], ["Publisher", "Book"])

    def test_resolve_func_classification(self):
        r = resolver_for(Book)
        avg = r.resolve_func(ir.Func("avg", (ir.Literal(1),)))
        self.assertEqual(avg.kind, ir.FuncKind.AGGREGATE)
        sumif = r.resolve_func(ir.Func("sumif", (ir.Literal(1),)))
        self.assertEqual(sumif.kind, ir.FuncKind.AGGREGATE)
        lower = r.resolve_func(ir.Func("lower", (ir.Literal("x"),)))
        self.assertEqual(lower.kind, ir.FuncKind.SCALAR)
        iif = r.resolve_func(ir.Func("iif", ()))
        self.assertEqual(iif.kind, ir.FuncKind.SCALAR)
        with self.assertRaises(UnknownFunctionException):
            r.resolve_func(ir.Func("no_such_function", ()))

    def test_group_by_from_aggregate(self):
        # publisher.name, avg(price)  ->  GROUP BY publisher.name
        q = ir.Query(
            model=Book,
            projections=[
                ir.Projection(ir.Name(("publisher", "name")), "publisher_name"),
                ir.Projection(ir.Func("avg", (ir.Name(("price",)),)), "avg"),
            ],
        )
        rq = resolver_for(Book).resolve(q)
        self.assertEqual(len(rq.group_by), 1)
        self.assertIsInstance(rq.group_by[0], ir.FieldRef)
        self.assertEqual(rq.group_by[0].column, "name")

    def test_no_group_by_without_aggregate(self):
        q = ir.Query(
            model=Book,
            projections=[ir.Projection(ir.Name(("name",)), "name")],
        )
        rq = resolver_for(Book).resolve(q)
        self.assertEqual(rq.group_by, [])
