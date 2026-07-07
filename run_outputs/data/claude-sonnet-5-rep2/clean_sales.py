import csv
from datetime import datetime
from collections import defaultdict

SRC = "sales_data.csv"
OUT = "cleaned_sales.csv"

DATE_FORMATS = [
    "%Y-%m-%d",   # ISO
    "%m/%d/%Y",   # M/D/YYYY
    "%m-%d-%Y",   # MM-DD-YYYY
    "%d %b %Y",   # D Mon YYYY
]

def parse_date(s):
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {s!r}")

def norm_title(s):
    return " ".join(s.strip().split()).title()

with open(SRC, newline="") as f:
    rows = list(csv.DictReader(f))

total_input_rows = len(rows)

# Remove exact duplicate rows (same values across all fields, as-is)
seen = set()
deduped = []
exact_dupes = 0
for row in rows:
    key = tuple(row.items())
    if key in seen:
        exact_dupes += 1
        continue
    seen.add(key)
    deduped.append(row)

kept = []
dropped_missing = 0

for row in deduped:
    units = row["units_sold"].strip()
    price = row["unit_price"].strip()
    if units == "" or price == "":
        dropped_missing += 1
        continue

    date = parse_date(row["order_date"])
    category = norm_title(row["category"])
    region = row["region"].strip()
    region = norm_title(region) if region else "Unknown"

    kept.append({
        "order_id": row["order_id"].strip(),
        "order_date": date.isoformat(),
        "category": category,
        "region": region,
        "units_sold": int(float(units)),
        "unit_price": float(price),
    })

with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["order_id", "order_date", "category", "region", "units_sold", "unit_price"])
    writer.writeheader()
    writer.writerows(kept)

# --- Analysis ---
total_kept = len(kept)
total_dropped = total_input_rows - total_kept

total_revenue = sum(r["units_sold"] * r["unit_price"] for r in kept)

revenue_by_category = defaultdict(float)
revenue_by_month = defaultdict(float)
for r in kept:
    rev = r["units_sold"] * r["unit_price"]
    revenue_by_category[r["category"]] += rev
    month = r["order_date"][:7]  # YYYY-MM
    revenue_by_month[month] += rev

cat_sorted = sorted(revenue_by_category.items(), key=lambda x: -x[1])
month_sorted = sorted(revenue_by_month.items())

with open("summary.md", "w") as f:
    f.write("# Sales Data Summary\n\n")
    f.write("## Row Counts\n\n")
    f.write(f"- Input rows: {total_input_rows}\n")
    f.write(f"- Exact duplicate rows removed: {exact_dupes}\n")
    f.write(f"- Rows dropped (missing units_sold or unit_price): {dropped_missing}\n")
    f.write(f"- Rows kept: {total_kept}\n")
    f.write(f"- Total rows dropped: {total_dropped}\n\n")

    f.write("## Total Revenue\n\n")
    f.write(f"${total_revenue:,.2f}\n\n")

    f.write("## Revenue by Category (descending)\n\n")
    f.write("| Category | Revenue |\n")
    f.write("|---|---|\n")
    for cat, rev in cat_sorted:
        f.write(f"| {cat} | ${rev:,.2f} |\n")
    f.write("\n")

    f.write("## Revenue by Month\n\n")
    f.write("| Month | Revenue |\n")
    f.write("|---|---|\n")
    for month, rev in month_sorted:
        f.write(f"| {month} | ${rev:,.2f} |\n")

print("Input rows:", total_input_rows)
print("Exact dupes removed:", exact_dupes)
print("Dropped (missing fields):", dropped_missing)
print("Kept:", total_kept)
print("Total revenue:", total_revenue)
