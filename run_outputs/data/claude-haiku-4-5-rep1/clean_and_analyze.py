import pandas as pd
from datetime import datetime
import re

# Read the CSV
df = pd.read_csv('sales_data.csv')

# Track original row count
original_count = len(df)

# 1. Remove duplicate rows (exact duplicates)
df = df.drop_duplicates()

# 2. Normalize dates to YYYY-MM-DD
def normalize_date(date_str):
    if pd.isna(date_str):
        return None

    date_str = str(date_str).strip()

    # Try different date formats
    formats = [
        '%Y-%m-%d',      # ISO: 2026-02-08
        '%m/%d/%Y',      # M/D/YYYY: 6/4/2026
        '%m-%d-%Y',      # MM-DD-YYYY: 04-10-2026
        '%d %b %Y',      # D Mon YYYY: 21 Mar 2026
    ]

    for fmt in formats:
        try:
            return pd.to_datetime(date_str, format=fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue

    return None

df['order_date'] = df['order_date'].apply(normalize_date)

# 3. Normalize category: title case and strip whitespace
df['category'] = df['category'].apply(
    lambda x: x.strip().title() if pd.notna(x) else x
)

# 4. Normalize region: title case, trim, set missing to "Unknown"
df['region'] = df['region'].apply(
    lambda x: x.strip().title() if pd.notna(x) and str(x).strip() else 'Unknown'
)

# 5. Drop rows missing units_sold OR unit_price
df = df.dropna(subset=['units_sold', 'unit_price'], how='any')

# Calculate rows kept and dropped
rows_kept = len(df)
rows_dropped = original_count - rows_kept

# 6. Calculate revenue
df['revenue'] = df['units_sold'] * df['unit_price']

# Write cleaned CSV
df.to_csv('cleaned_sales.csv', index=False)

# 7. Generate summary report
total_revenue = df['revenue'].sum()

# Revenue by category (sorted descending)
revenue_by_category = df.groupby('category')['revenue'].sum().sort_values(ascending=False)

# Revenue by month
df['month'] = pd.to_datetime(df['order_date']).dt.strftime('%Y-%m')
revenue_by_month = df.groupby('month')['revenue'].sum().sort_index()

# Write summary
with open('summary.md', 'w') as f:
    f.write("# Sales Data Analysis Summary\n\n")

    f.write("## Data Quality\n")
    f.write(f"- **Total rows kept:** {rows_kept}\n")
    f.write(f"- **Total rows dropped:** {rows_dropped}\n")
    f.write(f"- **Original row count:** {original_count}\n\n")

    f.write("## Total Revenue\n")
    f.write(f"${total_revenue:,.2f}\n\n")

    f.write("## Revenue by Category (Descending)\n")
    for category, revenue in revenue_by_category.items():
        f.write(f"- **{category}:** ${revenue:,.2f}\n")

    f.write("\n## Revenue by Month\n")
    for month, revenue in revenue_by_month.items():
        f.write(f"- **{month}:** ${revenue:,.2f}\n")

print(f"Cleaned data written to cleaned_sales.csv ({rows_kept} rows)")
print(f"Summary written to summary.md")
print(f"Rows dropped: {rows_dropped}")
