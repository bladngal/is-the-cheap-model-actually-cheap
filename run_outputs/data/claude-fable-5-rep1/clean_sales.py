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

# Remove exact duplicate rows (all raw fields identical), keeping first occurrence
seen = set()
deduped = []
for r in rows:
    raw_key = tuple(r.values())
    if raw_key in seen:
        continue
    seen.add(raw_key)
    deduped.append(r)

dup_dropped = total_read - len(deduped)

cleaned = []
missing_dropped = 0
for r in deduped:
    units = r["units_sold"].strip()
    price = r["unit_price"].strip()
    if not units or not price:
        missing_dropped += 1
        continue
    region = r["region"].strip()
    cleaned.append({
        "order_id": r["order_id"].strip(),
        "order_date": parse_date(r["order_date"]).isoformat(),
        "category": r["category"].strip().title(),
        "region": region.title() if region else "Unknown",
        "units_sold": int(units),
        "unit_price": float(price),
    })

cleaned.sort(key=lambda r: (r["order_date"], r["order_id"]))

with open("cleaned_sales.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["order_id", "order_date", "category",
                                      "region", "units_sold", "unit_price"])
    w.writeheader()
    w.writerows(cleaned)

total_revenue = sum(r["units_sold"] * r["unit_price"] for r in cleaned)
by_category = defaultdict(float)
by_month = defaultdict(float)
for r in cleaned:
    rev = r["units_sold"] * r["unit_price"]
    by_category[r["category"]] += rev
    by_month[r["order_date"][:7]] += rev

lines = [
    "# Sales Data Summary",
    "",
    "## Row Counts",
    "",
    f"- Rows in raw file: {total_read}",
    f"- Exact duplicate rows removed: {dup_dropped}",
    f"- Rows dropped for missing units_sold or unit_price: {missing_dropped}",
    f"- **Rows kept: {len(cleaned)}** (dropped: {dup_dropped + missing_dropped})",
    "",
    "## Total Revenue",
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
lines += [
    "",
    "## Revenue by Month",
    "",
    "| Month | Revenue |",
    "|---|---:|",
]
for month in sorted(by_month):
    lines.append(f"| {month} | ${by_month[month]:,.2f} |")
lines.append("")

with open("summary.md", "w") as f:
    f.write("\n".join(lines))

print(f"read={total_read} dups={dup_dropped} missing={missing_dropped} kept={len(cleaned)}")
print(f"revenue={total_revenue:,.2f}")
print("categories:", sorted(by_category))
