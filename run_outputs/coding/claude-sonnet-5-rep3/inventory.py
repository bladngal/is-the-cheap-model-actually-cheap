"""Simple inventory management library."""


class InsufficientStockError(Exception):
    pass


class Inventory:
    def __init__(self):
        # name -> {"qty": int, "price": float}
        self.items = {}

    def add_item(self, name, qty, price):
        """Add qty of an item. If it exists, increase qty (price unchanged)."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        if name in self.items:
            self.items[name]["qty"] += qty
        else:
            self.items[name] = {"qty": qty, "price": price}

    def remove_item(self, name, qty):
        """Remove qty of an item. Raises InsufficientStockError if not enough stock.
        Removes the item entirely when quantity reaches zero."""
        if name not in self.items:
            raise KeyError(name)
        if self.items[name]["qty"] > qty:
            self.items[name]["qty"] -= qty
        elif self.items[name]["qty"] == qty:
            del self.items[name]
        else:
            raise InsufficientStockError(name)

    def total_value(self):
        """Total value of inventory: sum of qty * price for each item."""
        total = 0
        for item in self.items.values():
            total += item["qty"] * item["price"]
        return total

    def low_stock(self, threshold):
        """Return sorted list of item names with qty <= threshold."""
        result = []
        for name, item in self.items.items():
            if item["qty"] <= threshold:
                result.append(name)
        return sorted(result)

    def apply_discount(self, pct):
        """Reduce every item's price by pct percent (e.g. 10 -> 10% off)."""
        for item in self.items.values():
            item["price"] = item["price"] * (1 - pct / 100)
