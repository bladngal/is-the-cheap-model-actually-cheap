#!/usr/bin/env python3
"""Clean and analyze the messy sales_data.csv export."""
import csv
import re
from collections import defaultdict, OrderedDict

SRC = "sales_data.csv"
OUT = "cleaned_sales.csv"
SUMMARY = "summary.md"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def normalize_date(raw):
    """Return YYYY-MM-DD for the four known input shapes, else None."""
    s = raw.strip()
    if not s:
        return None
    # ISO: 2026-02-08  (4-digit year first)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
    else:
        # MM-DD-YYYY or M/D/YYYY  (4-digit year last)
        m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
        if m:
            mo, d, y = m.groups()
        else:
            # "D Mon YYYY", e.g. 21 Mar 2026
            m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})", s)
            if not m:
                return None
            d, mon, y = m.groups()
            mo = MONTHS.get(mon[:3].lower())
            if mo is None:
                return None
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def parse_number(raw):
    """Return float if the field holds a value, else None for blanks."""
    s = raw.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --- Read + dedupe exact raw rows -------------------------------------------
with open(SRC, newline="") as f:
    reader = csv.reader(f)
    header = next(reader)
    seen = set()
    raw_rows = []
    for row in reader:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        raw_rows.append(row)

total_after_dedupe = len(raw_rows)

# --- Clean each row ----------------------------------------------------------
cleaned = []
dropped = 0
for order_id, order_date, category, region, units_sold, unit_price in raw_rows:
    date = normalize_date(order_date)
    units = parse_number(units_sold)
    price = parse_number(unit_price)

    # Spec: drop rows missing units_sold OR unit_price
    if units is None or price is None:
        dropped += 1
        continue

    cat = category.strip().title()
    reg = region.strip().title() or "Unknown"

    cleaned.append({
        "order_id": order_id.strip(),
        "order_date": date if date else "",
        "category": cat,
        "region": reg,
        "units_sold": units,
        "unit_price": price,
        "revenue": units * price,
    })

# --- Write cleaned_sales.csv -------------------------------------------------
fields = ["order_id", "order_date", "category", "region", "units_sold", "unit_price"]
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in cleaned:
        w.writerow({
            "order_id": r["order_id"],
            "order_date": r["order_date"],
            "category": r["category"],
            "region": r["region"],
            # emit integers cleanly, keep prices as given
            "units_sold": int(r["units_sold"]) if r["units_sold"].is_integer() else r["units_sold"],
            "unit_price": r["unit_price"],
        })

# --- Analysis ----------------------------------------------------------------
total_revenue = sum(r["revenue"] for r in cleaned)

rev_by_cat = defaultdict(float)
for r in cleaned:
    rev_by_cat[r["category"]] += r["revenue"]
rev_by_cat = sorted(rev_by_cat.items(), key=lambda kv: kv[1], reverse=True)

rev_by_month = defaultdict(float)
for r in cleaned:
    month = r["order_date"][:7] if r["order_date"] else "Unknown"
    rev_by_month[month] += r["revenue"]
rev_by_month = sorted(rev_by_month.items())

# --- Write summary.md --------------------------------------------------------
lines = []
lines.append("# Sales Data Summary\n")
lines.append("## Row counts\n")
lines.append(f"- Rows kept: **{len(cleaned)}**")
lines.append(f"- Rows dropped (missing units_sold or unit_price): **{dropped}**")
lines.append(f"- Exact duplicate rows removed: **{285 - total_after_dedupe}**")
lines.append("")
lines.append(f"## Total revenue\n\n**${total_revenue:,.2f}**\n")
lines.append("## Revenue by category (descending)\n")
lines.append("| Category | Revenue |")
lines.append("| --- | ---: |")
for cat, rev in rev_by_cat:
    lines.append(f"| {cat} | ${rev:,.2f} |")
lines.append("")
lines.append("## Revenue by month\n")
lines.append("| Month | Revenue |")
lines.append("| --- | ---: |")
for month, rev in rev_by_month:
    lines.append(f"| {month} | ${rev:,.2f} |")
lines.append("")

with open(SUMMARY, "w") as f:
    f.write("\n".join(lines))

# --- Console recap -----------------------------------------------------------
print(f"Source data rows (excl. header): 285")
print(f"After removing exact duplicates: {total_after_dedupe}")
print(f"Rows dropped (missing units/price): {dropped}")
print(f"Rows kept: {len(cleaned)}")
print(f"Total revenue: ${total_revenue:,.2f}")
print("Top categories:")
for cat, rev in rev_by_cat:
    print(f"  {cat:12s} ${rev:,.2f}")
