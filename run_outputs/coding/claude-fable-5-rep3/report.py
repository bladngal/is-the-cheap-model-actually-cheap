"""Reporting utilities for the inventory library."""

from inventory import Inventory


def format_report(inv: Inventory):
    """Return a list of report lines, one per item, sorted by name.

    Each line: "<name>: qty=<qty> price=$<price:.2f> value=$<qty*price:.2f>"
    """
    lines = []
    names = sorted(inv.items.keys())
    for name in names:
        item = inv.items[name]
        value = item["qty"] * item["price"]
        lines.append(
            f"{name}: qty={item['qty']} price=${item['price']:.2f} value=${value:.2f}"
        )
    return lines


def restock_list(inv: Inventory, threshold):
    """Return a single comma-separated string of items at or below threshold,
    e.g. "apples, pears". Returns "" when nothing is low."""
    low = inv.low_stock(threshold)
    return ", ".join(low)


def summary(inv: Inventory):
    """Return dict with item_count (distinct items), total_units, total_value."""
    total_units = 0
    for item in inv.items.values():
        total_units += item["qty"]
    return {
        "item_count": len(inv.items),
        "total_units": total_units,
        "total_value": inv.total_value(),
    }
