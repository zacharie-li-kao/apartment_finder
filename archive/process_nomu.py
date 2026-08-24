#!/usr/bin/env python3
import csv
import re
from collections import defaultdict

INPUT_FILE = r"C:\Users\zakat\Desktop\apartment\NOMU_10WARDS_RESULTS.tsv"

# Read the TSV
data = []
with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for row in reader:
        data.append(row)

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print(f"Total rows: {len(data)}")

# Function to extract clean property name from malformed Name field
def extract_clean_name(name_field):
    """Extract the actual property name from malformed listings"""
    if name_field.startswith('中古マンション'):
        # Pattern: 中古マンション<NAME><PRICE>万円...
        # Find where the price starts (ends with 万円)
        match = re.match(r'中古マンション(.+?)(\d+,?\d+万円)', name_field)
        if match:
            return match.group(1).strip()
    return name_field.strip()

# Clean all names
cleaned_data = []
quality_issues = defaultdict(list)

for idx, row in enumerate(data, start=2):  # Start at 2 (line 2 is first data row)
    # Extract clean name
    raw_name = row['Name']
    clean_name = extract_clean_name(raw_name)

    # Check for quality issues
    issues = []

    # Check if Name field was malformed
    if raw_name.startswith('中古マンション') and len(raw_name) > 50:
        issues.append("malformed_name_field")

    # Check for missing data
    if not row.get('Price (万円)') or row.get('Price (万円)').strip() == '':
        issues.append("missing_price")
    if not row.get('Size (m²)') or row.get('Size (m²)').strip() == '':
        issues.append("missing_size")
    if not row.get('Floor') or row.get('Floor').strip() == '':
        issues.append("missing_floor")
    if not row.get('Fees (¥/mo)') or row.get('Fees (¥/mo)').strip() == '' or row.get('Fees (¥/mo)') == 'N/A':
        issues.append("missing_fees")

    # Check for price anomalies (exactly 40M)
    if row.get('Price (万円)'):
        try:
            price = int(float(row.get('Price (万円)').strip()))
            if price == 4000:
                issues.append("edge_case_40M_yen")
        except:
            issues.append("price_parse_error")

    # Check layout
    if row.get('Layout') and row.get('Layout').strip() == '':
        issues.append("missing_layout")

    row_with_clean_name = dict(row)
    row_with_clean_name['_clean_name'] = clean_name
    row_with_clean_name['_issues'] = issues
    row_with_clean_name['_line_num'] = idx

    cleaned_data.append(row_with_clean_name)

    if issues:
        quality_issues[clean_name].extend(issues)

# Deduplicate by clean name
unique_properties = {}
duplicates_count = defaultdict(int)

for row in cleaned_data:
    clean_name = row['_clean_name']
    if clean_name not in unique_properties:
        unique_properties[clean_name] = row
    duplicates_count[clean_name] += 1

print(f"\nUnique properties: {len(unique_properties)}")
print(f"Duplication ratio: {len(data)} rows -> {len(unique_properties)} unique")

# Find most duplicated
print("\nTop 10 most duplicated properties:")
for name, count in sorted(duplicates_count.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {name}: {count} instances")

# Quality issues summary
print("\n=== QUALITY ISSUES ===")
properties_with_issues = {k: v for k, v in quality_issues.items() if v}
print(f"Properties with quality issues: {len(properties_with_issues)}")

issue_types = defaultdict(int)
for issues_list in quality_issues.values():
    for issue in issues_list:
        issue_types[issue] += 1

print("\nIssue breakdown:")
for issue, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {issue}: {count}")

# Sample top 20 unique verified properties (sorted by price)
print("\n=== TOP 20 UNIQUE VERIFIED PROPERTIES (by price) ===")
print("Name | Price | Size | Floor | Year | Walk | Station | Fees | Layout | Direction | Ownership")
print("-" * 150)

sorted_by_price = sorted(
    unique_properties.values(),
    key=lambda x: float(x.get('Price (万円)', 0)) if x.get('Price (万円)') else float('inf')
)

count = 0
for prop in sorted_by_price:
    if not prop.get('_issues'):  # Only show verified properties
        name = prop['_clean_name'][:20]
        price = prop.get('Price (万円)', '')
        size = prop.get('Size (m²)', '')
        floor = prop.get('Floor', '')
        year = prop.get('Year', '')
        walk = prop.get('Walk (min)', '')
        station = prop.get('Station', '')
        fees = prop.get('Fees (¥/mo)', '')
        layout = prop.get('Layout', '')
        direction = prop.get('Direction', '')
        ownership = prop.get('Ownership', '')

        print(f"{name:20} | {price:6} | {size:6} | {floor:6} | {year:5} | {walk:5} | {station:10} | {fees:10} | {layout:6} | {direction:6} | {ownership}")
        count += 1
        if count >= 20:
            break

# Final count and summary
print(f"\n=== FINAL SUMMARY ===")
print(f"Total rows in file: {len(data)}")
print(f"Unique properties after deduplication: {len(unique_properties)}")
print(f"Properties with quality issues: {len(properties_with_issues)}")
print(f"Clean verified properties: {len(unique_properties) - len(properties_with_issues)}")
