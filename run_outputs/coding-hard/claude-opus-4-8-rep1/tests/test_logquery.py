import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logquery import tokenize, parse, match, run_query, aggregate, top_n


RECORDS = [
    {"level": "ERROR", "service": "api", "latency_ms": 120, "msg": "db timeout", "ts": "2026-01-03"},
    {"level": "INFO", "service": "api", "latency_ms": 30, "msg": "ok", "ts": "2026-01-04"},
    {"level": "ERROR", "service": "web", "latency_ms": 450, "msg": "upstream 502", "ts": "2026-02-01"},
    {"level": "WARN", "service": "web", "latency_ms": 80, "msg": "slow render", "ts": "2026-02-02"},
    {"level": "ERROR", "service": "worker", "latency_ms": 9.5, "msg": "retry limit", "ts": "2026-02-03"},
    {"level": "INFO", "service": "worker", "msg": "job done", "ts": "2026-03-01"},
    {"level": "DEBUG", "service": "api", "latency_ms": 5, "msg": "cache hit", "ts": "2026-03-02"},
]


class TestTokenize(unittest.TestCase):
    def test_simple_comparison(self):
        self.assertEqual(
            tokenize("level=ERROR"),
            [("word", "level"), ("op", "="), ("word", "ERROR")],
        )

    def test_all_operators(self):
        for op in ["=", "!=", ">", ">=", "<", "<="]:
            with self.subTest(op=op):
                self.assertEqual(tokenize(f"a{op}b")[1], ("op", op))

    def test_keywords_case_insensitive(self):
        self.assertEqual(
            tokenize("a=1 AND b=2 or NOT c=3"),
            [
                ("word", "a"), ("op", "="), ("word", "1"),
                ("kw", "and"),
                ("word", "b"), ("op", "="), ("word", "2"),
                ("kw", "or"),
                ("kw", "not"),
                ("word", "c"), ("op", "="), ("word", "3"),
            ],
        )

    def test_quoted_value_with_spaces(self):
        self.assertEqual(
            tokenize('msg="db timeout"'),
            [("word", "msg"), ("op", "="), ("word", "db timeout")],
        )

    def test_quoted_value_with_escaped_quote(self):
        self.assertEqual(tokenize('msg="say \\"hi\\""')[-1], ("word", 'say "hi"'))

    def test_parens(self):
        self.assertEqual(
            tokenize("(a=1)"),
            [("lparen",), ("word", "a"), ("op", "="), ("word", "1"), ("rparen",)],
        )

    def test_bad_character_raises(self):
        with self.assertRaises(ValueError):
            tokenize("a=1 & b=2")


class TestParse(unittest.TestCase):
    def test_single_comparison(self):
        ast = parse(tokenize("level=ERROR"))
        self.assertEqual(ast, ("cmp", "level", "=", "ERROR"))

    def test_and_or_precedence(self):
        # a=1 OR b=2 AND c=3  ==  a=1 OR (b=2 AND c=3)
        ast = parse(tokenize("a=1 OR b=2 AND c=3"))
        self.assertEqual(ast[0], "or")
        self.assertEqual(ast[1], ("cmp", "a", "=", "1"))
        self.assertEqual(ast[2][0], "and")

    def test_not_binds_tightest(self):
        # NOT a=1 AND b=2  ==  (NOT a=1) AND b=2
        ast = parse(tokenize("NOT a=1 AND b=2"))
        self.assertEqual(ast[0], "and")
        self.assertEqual(ast[1], ("not", ("cmp", "a", "=", "1")))

    def test_parens_override_precedence(self):
        ast = parse(tokenize("(a=1 OR b=2) AND c=3"))
        self.assertEqual(ast[0], "and")
        self.assertEqual(ast[1][0], "or")

    def test_double_not(self):
        ast = parse(tokenize("NOT NOT a=1"))
        self.assertEqual(ast, ("not", ("not", ("cmp", "a", "=", "1"))))

    def test_missing_rparen_raises(self):
        with self.assertRaises(ValueError):
            parse(tokenize("(a=1 AND b=2"))

    def test_trailing_tokens_raise(self):
        with self.assertRaises(ValueError):
            parse(tokenize("a=1 b=2"))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            parse([])


class TestMatch(unittest.TestCase):
    def test_string_equality(self):
        ast = parse(tokenize("level=ERROR"))
        self.assertTrue(match(RECORDS[0], ast))
        self.assertFalse(match(RECORDS[1], ast))

    def test_numeric_comparison(self):
        ast = parse(tokenize("latency_ms>100"))
        self.assertTrue(match(RECORDS[0], ast))   # 120
        self.assertFalse(match(RECORDS[1], ast))  # 30

    def test_numeric_not_lexicographic(self):
        # "9.5" > "100" lexicographically, but 9.5 < 100 numerically
        ast = parse(tokenize("latency_ms>100"))
        self.assertFalse(match(RECORDS[4], ast))  # 9.5

    def test_missing_field_is_false_even_for_ne(self):
        ast = parse(tokenize("latency_ms!=5"))
        self.assertFalse(match(RECORDS[5], ast))  # no latency_ms key

    def test_date_range_as_strings(self):
        ast = parse(tokenize("ts>=2026-02-01 AND ts<2026-03-01"))
        matching = [r for r in RECORDS if match(r, ast)]
        self.assertEqual(len(matching), 3)

    def test_not(self):
        ast = parse(tokenize("NOT level=ERROR"))
        self.assertEqual(sum(match(r, ast) for r in RECORDS), 4)


class TestRunQuery(unittest.TestCase):
    def test_compound_query(self):
        out = run_query(RECORDS, "level=ERROR AND (service=api OR service=web)")
        self.assertEqual(len(out), 2)
        self.assertEqual({r["service"] for r in out}, {"api", "web"})

    def test_quoted_message(self):
        out = run_query(RECORDS, 'msg="db timeout"')
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["service"], "api")

    def test_no_matches(self):
        self.assertEqual(run_query(RECORDS, "service=billing"), [])


class TestAggregate(unittest.TestCase):
    def test_counts_by_level(self):
        self.assertEqual(
            aggregate(RECORDS, "level"),
            {"ERROR": 3, "INFO": 2, "WARN": 1, "DEBUG": 1},
        )

    def test_missing_field_skipped(self):
        counts = aggregate(RECORDS, "latency_ms")
        self.assertEqual(sum(counts.values()), 6)  # one record lacks it

    def test_top_n_order_and_ties(self):
        # INFO=2, WARN=1, DEBUG=1 -> tie between DEBUG and WARN broken by value
        self.assertEqual(
            top_n(RECORDS, "level", 3),
            [("ERROR", 3), ("INFO", 2), ("DEBUG", 1)],
        )

    def test_top_n_truncates(self):
        self.assertEqual(len(top_n(RECORDS, "service", 2)), 2)


if __name__ == "__main__":
    unittest.main()
