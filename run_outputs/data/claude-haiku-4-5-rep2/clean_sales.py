import csv
from datetime import datetime
from collections import defaultdict

# Parse date in various formats
def parse_date(date_str):
    if not date_str or date_str.strip() == '':
        return None

    date_str = date_str.strip()
    formats = [
        '%Y-%m-%d',      # ISO format
        '%m/%d/%Y',      # M/D/YYYY
        '%m-%d-%Y',      # MM-DD-YYYY
        '%d %b %Y',      # D Mon YYYY
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None

# Normalize category: title case and trim whitespace
def normalize_category(cat):
    if not cat or cat.strip() == '':
        return None
    return cat.strip().title()

# Normalize region: title case, trim whitespace, handle missing
def normalize_region(reg):
    if not reg or reg.strip() == '':
        return 'Unknown'
    return reg.strip().title()

# Read raw data
rows = []
with open('sales_data.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

initial_rows = len(rows)
print(f"Data rows before cleaning: {initial_rows}")

# Clean and validate rows
cleaned_rows = []
seen = set()

for row in rows:
    # Parse and normalize date
    order_date = parse_date(row['order_date'])
    if not order_date:
        continue

    # Normalize category
    category = normalize_category(row['category'])
    if not category:
        continue

    # Normalize region
    region = normalize_region(row['region'])

    # Parse units_sold and unit_price
    try:
        units_sold = float(row['units_sold']) if row['units_sold'].strip() else None
        unit_price = float(row['unit_price']) if row['unit_price'].strip() else None
    except (ValueError, AttributeError):
        units_sold = None
        unit_price = None

    # Skip if missing units_sold or unit_price
    if units_sold is None or unit_price is None:
        continue

    # Convert to int for units_sold if it's a whole number
    if units_sold == int(units_sold):
        units_sold = int(units_sold)

    # Create cleaned row
    cleaned_row = {
        'order_id': row['order_id'],
        'order_date': order_date,
        'category': category,
        'region': region,
        'units_sold': units_sold,
        'unit_price': unit_price
    }

    # Check for exact duplicates
    row_tuple = tuple(cleaned_row.values())
    if row_tuple in seen:
        continue
    seen.add(row_tuple)

    cleaned_rows.append(cleaned_row)

kept_rows = len(cleaned_rows)
dropped_rows = initial_rows - kept_rows

print(f"Rows kept: {kept_rows}")
print(f"Rows dropped: {dropped_rows}")

# Write cleaned CSV
with open('cleaned_sales.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['order_id', 'order_date', 'category', 'region', 'units_sold', 'unit_price'])
    writer.writeheader()
    writer.writerows(cleaned_rows)

print("Cleaned data written to cleaned_sales.csv")

# Calculate metrics
total_revenue = 0
revenue_by_category = defaultdict(float)
revenue_by_month = defaultdict(float)

for row in cleaned_rows:
    revenue = row['units_sold'] * row['unit_price']
    total_revenue += revenue

    category = row['category']
    revenue_by_category[category] += revenue

    month = row['order_date'][:7]  # YYYY-MM
    revenue_by_month[month] += revenue

# Sort category revenue descending
sorted_categories = sorted(revenue_by_category.items(), key=lambda x: x[1], reverse=True)

# Sort month revenue ascending
sorted_months = sorted(revenue_by_month.items())

# Write summary
with open('summary.md', 'w') as f:
    f.write('# Sales Data Summary\n\n')
    f.write(f'**Total Rows Kept:** {kept_rows}\n\n')
    f.write(f'**Total Rows Dropped:** {dropped_rows}\n\n')
    f.write(f'**Total Revenue:** ${total_revenue:,.2f}\n\n')

    f.write('## Revenue by Category (Descending)\n\n')
    for category, revenue in sorted_categories:
        f.write(f'- {category}: ${revenue:,.2f}\n')

    f.write('\n## Revenue by Month\n\n')
    for month, revenue in sorted_months:
        f.write(f'- {month}: ${revenue:,.2f}\n')

print("Summary written to summary.md")
