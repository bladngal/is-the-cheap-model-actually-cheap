import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inventory import Inventory, InsufficientStockError


class TestAddRemove(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()
        self.inv.add_item("apples", 10, 0.50)
        self.inv.add_item("pears", 4, 0.75)

    def test_add_new_item(self):
        self.inv.add_item("plums", 3, 1.25)
        self.assertEqual(self.inv.items["plums"]["qty"], 3)

    def test_add_existing_increases_qty(self):
        self.inv.add_item("apples", 5, 0.50)
        self.assertEqual(self.inv.items["apples"]["qty"], 15)

    def test_add_rejects_nonpositive_qty(self):
        with self.assertRaises(ValueError):
            self.inv.add_item("figs", 0, 2.0)

    def test_remove_partial(self):
        self.inv.remove_item("apples", 4)
        self.assertEqual(self.inv.items["apples"]["qty"], 6)

    def test_remove_exact_quantity_removes_item(self):
        self.inv.remove_item("pears", 4)
        self.assertNotIn("pears", self.inv.items)

    def test_remove_too_many_raises(self):
        with self.assertRaises(InsufficientStockError):
            self.inv.remove_item("pears", 5)

    def test_remove_unknown_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.inv.remove_item("dragonfruit", 1)


class TestValueAndStock(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()
        self.inv.add_item("apples", 10, 0.50)   # value 5.00
        self.inv.add_item("pears", 4, 0.75)     # value 3.00
        self.inv.add_item("cherries", 2, 3.00)  # value 6.00

    def test_total_value(self):
        self.assertAlmostEqual(self.inv.total_value(), 14.00)

    def test_low_stock_returns_items_at_or_below_threshold(self):
        self.assertEqual(self.inv.low_stock(4), ["cherries", "pears"])

    def test_low_stock_empty_when_all_above(self):
        self.assertEqual(self.inv.low_stock(1), [])

    def test_apply_discount_reduces_prices(self):
        self.inv.apply_discount(10)
        self.assertAlmostEqual(self.inv.items["apples"]["price"], 0.45)
        self.assertAlmostEqual(self.inv.items["cherries"]["price"], 2.70)


if __name__ == "__main__":
    unittest.main()
