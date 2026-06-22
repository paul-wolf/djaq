"""Unit tests for dialect rendering and IN-list expansion (no database)."""

import unittest

from djaq.query.generator import PostgresDialect, SQLiteDialect, SQLGenerator, get_dialect


class TestDialects(unittest.TestCase):
    def setUp(self):
        self.pg = PostgresDialect()
        self.lite = SQLiteDialect()

    def test_cast(self):
        self.assertEqual(self.pg.cast("price", "int"), "price::int")
        self.assertEqual(self.lite.cast("price", "int"), "CAST(price AS int)")

    def test_date_extract(self):
        self.assertEqual(self.pg.date_extract("year", "col"), "date_part('year', col)")
        self.assertEqual(
            self.lite.date_extract("year", "col"),
            "CAST(strftime('%Y', col) AS INTEGER)",
        )
        # DateTimeField .date is DATE() on both
        self.assertEqual(self.pg.date_extract("date", "col"), "DATE(col)")
        self.assertEqual(self.lite.date_extract("date", "col"), "DATE(col)")

    def test_regex_and_ilike(self):
        self.assertEqual(self.pg.render_function("regex", ["a", "b"]), "a ~ b")
        self.assertEqual(self.lite.render_function("regex", ["a", "b"]), "a REGEXP b")
        self.assertEqual(self.pg.render_function("ilike", ["a", "b"]), "a ILIKE b")
        self.assertEqual(self.lite.render_function("ilike", ["a", "b"]), "a LIKE b")

    def test_concat_is_portable(self):
        for d in (self.pg, self.lite):
            self.assertEqual(d.render_function("concat", ["a", "b"]), "a || b")

    def test_offset_without_limit(self):
        # Postgres allows bare OFFSET; SQLite needs a LIMIT
        self.assertEqual(self.pg.limit_offset(None, 7), " OFFSET 7")
        self.assertEqual(self.lite.limit_offset(None, 7), " LIMIT -1 OFFSET 7")
        # falsy limit/offset means "unset"
        self.assertEqual(self.lite.limit_offset(0, 0), "")

    def test_unknown_function_generic(self):
        self.assertEqual(self.pg.render_function("lower", ["x"]), "LOWER(x)")

    def test_get_dialect(self):
        self.assertIsInstance(get_dialect("postgresql"), PostgresDialect)
        self.assertIsInstance(get_dialect("sqlite"), SQLiteDialect)


class TestInListExpansion(unittest.TestCase):
    def expand(self, value):
        gen = SQLGenerator(PostgresDialect())
        gen.context = {"ids": value}
        gen.extra_named = {}
        result = gen._expand_in_list("ids")
        return result, gen.extra_named

    def test_list_expands_to_named_placeholders(self):
        result, extra = self.expand([10, 20, 30])
        self.assertEqual(result, "%(ids__0)s, %(ids__1)s, %(ids__2)s")
        self.assertEqual(extra, {"ids__0": 10, "ids__1": 20, "ids__2": 30})

    def test_tuple_also_expands(self):
        result, extra = self.expand((1, 2))
        self.assertEqual(result, "%(ids__0)s, %(ids__1)s")

    def test_non_list_returns_none(self):
        # a scalar (or missing) value falls back to normal rendering
        result, extra = self.expand("not-a-list")
        self.assertIsNone(result)
        self.assertEqual(extra, {})


if __name__ == "__main__":
    unittest.main()
