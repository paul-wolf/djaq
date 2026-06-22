"""Unit tests for the dialect-neutral IR helpers (no database needed)."""

import unittest

from djaq.query import ir


class TestIR(unittest.TestCase):
    def test_children_leaves(self):
        for leaf in (
            ir.Literal(1),
            ir.Param("x"),
            ir.Name(("a", "b")),
            ir.FieldRef(relation=None, column="c"),
            ir.RawSQL("SELECT 1"),
        ):
            self.assertEqual(ir.children(leaf), ())

    def test_children_composites(self):
        a, b = ir.Literal(1), ir.Literal(2)
        self.assertEqual(ir.children(ir.BinaryOp(ir.Op.ADD, a, b)), (a, b))
        self.assertEqual(ir.children(ir.BoolOp(ir.BoolKind.AND, (a, b))), (a, b))
        self.assertEqual(ir.children(ir.Not(a)), (a,))
        self.assertEqual(ir.children(ir.Unary(ir.Op.SUB, a)), (a,))
        self.assertEqual(ir.children(ir.Func("avg", (a, b))), (a, b))
        self.assertEqual(ir.children(ir.TupleExpr((a, b))), (a, b))
        self.assertEqual(ir.children(ir.DateExtract("year", a)), (a,))

    def test_children_case(self):
        cond, res, default = ir.Literal(True), ir.Literal("y"), ir.Literal("n")
        case = ir.Case(whens=((cond, res),), default=default)
        self.assertEqual(ir.children(case), (cond, res, default))

    def test_walk_is_depthfirst_and_complete(self):
        # avg(price + 1)
        inner = ir.BinaryOp(ir.Op.ADD, ir.Name(("price",)), ir.Literal(1))
        tree = ir.Func("avg", (inner,))
        nodes = list(ir.walk(tree))
        self.assertIs(nodes[0], tree)
        self.assertIn(inner, nodes)
        self.assertEqual(len(nodes), 4)  # func, binop, name, literal

    def test_contains_aggregate(self):
        agg = ir.Func("avg", (ir.Name(("price",)),), kind=ir.FuncKind.AGGREGATE)
        scalar = ir.Func("lower", (ir.Name(("name",)),), kind=ir.FuncKind.SCALAR)
        self.assertTrue(ir.contains_aggregate(agg))
        self.assertFalse(ir.contains_aggregate(scalar))
        # nested aggregate inside an arithmetic expression
        expr = ir.BinaryOp(ir.Op.SUB, agg, ir.Literal(1))
        self.assertTrue(ir.contains_aggregate(expr))

    def test_sumif_is_aggregate_in_catalogue(self):
        # the bug this whole design fixes: sumif must always aggregate
        self.assertIn("sumif", ir.AGGREGATE_FUNCS)
        self.assertIn("countdistinct", ir.AGGREGATE_FUNCS)

    def test_unknown_node_raises(self):
        with self.assertRaises(TypeError):
            ir.children(object())


if __name__ == "__main__":
    unittest.main()
