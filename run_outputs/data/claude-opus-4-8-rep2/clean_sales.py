#!/usr/bin/env python3
"""Clean and analyze messy sales_data.csv."""
import csv
from collections import defaultdict
from datetime import datetime

SRC = "sales_data.csv"
OUT = "cleaned_sales.csv"
SUMMARY = "summary.md"

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def normalize_date(raw):
    """Return YYYY-MM-DD. Numeric forms are month-first; also handle 'D Mon YYYY'."""
    s = raw.strip()
    # ISO: YYYY-MM-DD
    if len(s) >= 10 and s[4] == "-" and s[:4].isdigit():
        return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")
    # Textual: "D Mon YYYY"
    parts = s.split()
    if len(parts) == 3 and parts[1][:3].title() in MONTHS:
        d, mon, y = int(parts[0]), MONTHS[parts[1][:3].title()], int(parts[2])
        return datetime(y, mon, d).strftime("%Y-%m-%d")
    # Month-first numeric: M/D/YYYY or MM-DD-YYYY
    sep = "/" if "/" in s else "-"
    m, d, y = (int(x) for x in s.split(sep))
    return datetime(y, m, d).strftime("%Y-%m-%d")


# --- Read + dedup exact raw rows (preserving order) ---
with open(SRC, newline="") as f:
    reader = csv.reader(f)
    header = next(reader)
    seen, rows = set(), []
    for row in reader:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

kept, dropped = [], 0
for order_id, order_date, category, region, units_sold, unit_price in rows:
    units_sold, unit_price = units_sold.strip(), unit_price.strip()
    if not units_sold or not unit_price:      # drop rows missing either numeric
        dropped += 1
        continue
    kept.append({
        "order_id": order_id.strip(),
        "order_date": normalize_date(order_date),
        "category": category.strip().title(),
        "region": region.strip().title() or "Unknown",
        "units_sold": int(units_sold),
        "unit_price": float(unit_price),
    })

# --- Write cleaned CSV ---
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=header)
    w.writeheader()
    for r in kept:
        w.writerow(r)

# --- Analysis ---
total_revenue = 0.0
rev_by_cat = defaultdict(float)
rev_by_month = defaultdict(float)
for r in kept:
    rev = r["units_sold"] * r["unit_price"]
    total_revenue += rev
    rev_by_cat[r["category"]] += rev
    rev_by_month[r["order_date"][:7]] += rev

lines = ["# Sales Data Summary", ""]
lines += [f"- **Rows kept:** {len(kept)}", f"- **Rows dropped:** {dropped}",
          f"- **Total revenue:** ${total_revenue:,.2f}", "",
          "## Revenue by Category (descending)", "",
          "| Category | Revenue |", "| --- | ---: |"]
for cat, rev in sorted(rev_by_cat.items(), key=lambda kv: kv[1], reverse=True):
    lines.append(f"| {cat} | ${rev:,.2f} |")
lines += ["", "## Revenue by Month", "", "| Month | Revenue |", "| --- | ---: |"]
for month in sorted(rev_by_month):
    lines.append(f"| {month} | ${rev_by_month[month]:,.2f} |")
lines.append("")

with open(SUMMARY, "w") as f:
    f.write("\n".join(lines))

print(f"kept={len(kept)} dropped={dropped} total_revenue={total_revenue:,.2f}")
print(f"unique rows after dedup={len(rows)} (from {len(seen)} keys)")
