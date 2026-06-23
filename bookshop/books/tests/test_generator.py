"""Unit tests for dialect rendering and IN-list expansion (no database)."""

import unittest

from djaq.query.generator import (
    PostgresDialect,
    SQLiteDialect,
    MySQLDialect,
    SQLGenerator,
    get_dialect,
)


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
        self.assertIsInstance(get_dialect("mysql"), MySQLDialect)


class TestMySQLDialect(unittest.TestCase):
    """String-level checks for the (server-unverified) MySQL dialect."""

    def setUp(self):
        self.d = MySQLDialect()

    def test_backtick_quoting(self):
        self.assertEqual(self.d.quote_ident("name"), "`name`")
        self.assertEqual(self.d.quote_table("books_book"), "`books_book`")

    def test_concat_uses_function(self):
        # || is logical OR in MySQL, so concat must use CONCAT()
        self.assertEqual(self.d.render_function("concat", ["a", "b"]), "CONCAT(a, b)")

    def test_ilike_and_regex(self):
        self.assertEqual(
            self.d.render_function("ilike", ["a", "b"]), "LOWER(a) LIKE LOWER(b)"
        )
        self.assertEqual(self.d.render_function("regex", ["a", "b"]), "a REGEXP b")

    def test_cast_remaps_type(self):
        # MySQL CAST rejects "int"; it must be SIGNED
        self.assertEqual(self.d.cast("price", "int"), "CAST(price AS SIGNED)")
        self.assertEqual(self.d.cast("name", "string"), "CAST(name AS CHAR)")

    def test_date_extract(self):
        self.assertEqual(self.d.date_extract("year", "col"), "EXTRACT(YEAR FROM col)")
        self.assertEqual(self.d.date_extract("date", "col"), "DATE(col)")

    def test_offset_requires_limit(self):
        self.assertEqual(
            self.d.limit_offset(None, 7), " LIMIT 18446744073709551615 OFFSET 7"
        )
        self.assertEqual(self.d.limit_offset(10, 5), " LIMIT 10 OFFSET 5")


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
