import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inventory import Inventory
from report import format_report, restock_list, summary


def build_inventory():
    inv = Inventory()
    inv.add_item("apples", 10, 0.50)
    inv.add_item("pears", 4, 0.75)
    inv.add_item("cherries", 2, 3.00)
    return inv


class TestFormatReport(unittest.TestCase):
    def test_sorted_by_name_ascending(self):
        lines = format_report(build_inventory())
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("apples:"))
        self.assertTrue(lines[1].startswith("cherries:"))
        self.assertTrue(lines[2].startswith("pears:"))

    def test_line_format(self):
        lines = format_report(build_inventory())
        self.assertEqual(lines[0], "apples: qty=10 price=$0.50 value=$5.00")


class TestRestockList(unittest.TestCase):
    def test_comma_space_separated(self):
        self.assertEqual(restock_list(build_inventory(), 4), "cherries, pears")

    def test_empty_when_none_low(self):
        self.assertEqual(restock_list(build_inventory(), 0), "")


class TestSummary(unittest.TestCase):
    def test_summary_fields(self):
        s = summary(build_inventory())
        self.assertEqual(s["item_count"], 3)
        self.assertEqual(s["total_units"], 16)
        self.assertAlmostEqual(s["total_value"], 14.00)


if __name__ == "__main__":
    unittest.main()
