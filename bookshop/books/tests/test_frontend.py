"""Unit tests for the frontend: Djaq source -> unresolved IR (no database)."""

import unittest

from djaq.query import ir
from djaq.query import frontend


def expr(src):
    return frontend.convert_expression(src)


class TestFrontend(unittest.TestCase):
    def test_split_columns_respects_parens(self):
        self.assertEqual(
            list(frontend.split_columns("a, f(x, y), b")),
            ["a", "f(x, y)", "b"],
        )

    def test_column_aliases(self):
        self.assertEqual(
            frontend.parse_column_aliases("(name, price as p, publisher.name)"),
            [("name", "name"), ("price", "p"), ("publisher.name", "publisher_name")],
        )

    def test_literals(self):
        self.assertEqual(expr("1"), ir.Literal(1))
        self.assertEqual(expr("'hi'"), ir.Literal("hi"))
        self.assertEqual(expr("True"), ir.Literal(True))
        self.assertEqual(expr("None"), ir.Literal(None))

    def test_name_and_attribute(self):
        self.assertEqual(expr("name"), ir.Name(("name",)))
        self.assertEqual(expr("publisher.owner.name"), ir.Name(("publisher", "owner", "name")))

    def test_param_placeholder(self):
        self.assertEqual(expr("{discount}"), ir.Param("discount"))

    def test_named_ref_and_rawsql(self):
        self.assertEqual(expr("'@v_sub'"), ir.NamedRef("v_sub"))
        self.assertIsInstance(expr("'SELECT 1'"), ir.RawSQL)

    def test_arithmetic_and_compare(self):
        e = expr("price * 2")
        self.assertEqual(e, ir.BinaryOp(ir.Op.MUL, ir.Name(("price",)), ir.Literal(2)))
        c = expr("rating >= 3")
        self.assertEqual(c.op, ir.Op.GE)

    def test_chained_compare(self):
        e = expr("1 < x < 10")
        self.assertIsInstance(e, ir.BoolOp)
        self.assertEqual(e.kind, ir.BoolKind.AND)
        self.assertEqual(len(e.operands), 2)

    def test_boolop(self):
        e = expr("a == 1 or b == 2")
        self.assertIsInstance(e, ir.BoolOp)
        self.assertEqual(e.kind, ir.BoolKind.OR)

    def test_in_and_not_in(self):
        self.assertEqual(expr("rating in (0, 1)").op, ir.Op.IN)
        self.assertEqual(expr("rating not in (0, 1)").op, ir.Op.NOT_IN)

    def test_func(self):
        e = expr("sumif(rating > 3, 1, 0)")
        self.assertIsInstance(e, ir.Func)
        self.assertEqual(e.name, "sumif")
        self.assertEqual(len(e.args), 3)

    def test_negation(self):
        self.assertEqual(expr("-id"), ir.Unary(ir.Op.SUB, ir.Name(("id",))))

    def test_parse_query(self):
        q = frontend.parse(
            model="<model>",
            select_src="(name, avg(price) as ap)",
            where_src="price > 7",
            order_by_src="-name, id",
        )
        self.assertEqual(len(q.projections), 2)
        self.assertEqual(q.projections[1].alias, "ap")
        self.assertIsInstance(q.where, ir.BinaryOp)
        self.assertEqual(q.order_by[0].direction, ir.Direction.DESC)
        self.assertEqual(q.order_by[1].direction, ir.Direction.ASC)


if __name__ == "__main__":
    unittest.main()
