import csv
from datetime import datetime
from collections import defaultdict

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d %b %Y", "%m-%d-%Y"]

def parse_date(raw):
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {raw!r}")

with open("sales_data.csv", newline="") as f:
    rows = list(csv.DictReader(f))

total_read = len(rows)

# Remove exact duplicates (on the raw, pre-cleaning values) preserving order
seen = set()
deduped = []
for r in rows:
    key = tuple(r[c].strip() for c in r)
    if key not in seen:
        seen.add(key)
        deduped.append(r)
dup_dropped = total_read - len(deduped)

kept, missing_dropped = [], 0
for r in deduped:
    units, price = r["units_sold"].strip(), r["unit_price"].strip()
    if not units or not price:
        missing_dropped += 1
        continue
    kept.append({
        "order_id": r["order_id"].strip(),
        "order_date": parse_date(r["order_date"]).isoformat(),
        "category": r["category"].strip().title(),
        "region": r["region"].strip().title() or "Unknown",
        "units_sold": int(units),
        "unit_price": float(price),
    })

fields = ["order_id", "order_date", "category", "region", "units_sold", "unit_price"]
with open("cleaned_sales.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(kept)

total_revenue = sum(r["units_sold"] * r["unit_price"] for r in kept)
by_category = defaultdict(float)
by_month = defaultdict(float)
for r in kept:
    rev = r["units_sold"] * r["unit_price"]
    by_category[r["category"]] += rev
    by_month[r["order_date"][:7]] += rev

lines = [
    "# Sales Data Summary",
    "",
    "## Row Counts",
    "",
    f"- Rows in source file: {total_read}",
    f"- Exact duplicate rows removed: {dup_dropped}",
    f"- Rows dropped for missing units_sold or unit_price: {missing_dropped}",
    f"- **Rows kept: {len(kept)}** (total dropped: {dup_dropped + missing_dropped})",
    "",
    f"## Total Revenue",
    "",
    f"**${total_revenue:,.2f}**",
    "",
    "## Revenue by Category",
    "",
    "| Category | Revenue |",
    "|---|---:|",
]
for cat, rev in sorted(by_category.items(), key=lambda kv: -kv[1]):
    lines.append(f"| {cat} | ${rev:,.2f} |")
lines += ["", "## Revenue by Month", "", "| Month | Revenue |", "|---|---:|"]
for month in sorted(by_month):
    lines.append(f"| {month} | ${by_month[month]:,.2f} |")
lines.append("")

with open("summary.md", "w") as f:
    f.write("\n".join(lines))

print(f"read={total_read} dupes={dup_dropped} missing={missing_dropped} kept={len(kept)}")
print(f"revenue={total_revenue:,.2f}")
