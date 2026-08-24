#!/usr/bin/env python3
"""
Filter new SUUMO listings against strict criteria.
"""

import json
import re
from pathlib import Path
from typing import List, Dict

# User criteria
CRITERIA = {
    "min_price": 15000000,    # 1500万
    "max_price": 40000000,    # 4000万
    "min_size": 30.0,         # m²
    "min_year": 1982,
    "max_walk": 15,           # minutes
    "min_layout": "1LDK",     # Must be 1LDK or better
}

def parse_price(price_str):
    """Convert '2380万円' to integer yen."""
    if not price_str or '万円' not in price_str:
        return None
    try:
        return int(price_str.replace('万円', '')) * 10000
    except:
        return None

def parse_size(size_str):
    """Convert size string to float."""
    if not size_str:
        return None
    try:
        return float(size_str)
    except:
        return None

def parse_year(year_str):
    """Convert '2021年9月' to year integer."""
    if not year_str:
        return None
    try:
        match = re.search(r'(\d{4})', year_str)
        if match:
            return int(match.group(1))
    except:
        pass
    return None

def parse_walk(walk_str):
    """Convert walk time to integer."""
    if not walk_str:
        return None
    try:
        return int(walk_str)
    except:
        return None

def check_layout(layout_str):
    """Check if layout meets minimum (1LDK or better)."""
    if not layout_str:
        return False

    # Normalize
    layout = layout_str.strip().upper()

    # Disqualify: studio, ワンルーム, K, DK, 1DK (these are all less than 1LDK)
    if layout in ['ワンルーム', '1DK', '1K']:
        return False

    # Check for at least 2K, 1LDK, 2LDK, 3LDK, 4LDK, etc., or 2DK
    valid = [
        '1LDK', '2K', '2DK', '2LDK',
        '3LDK', '3DK', '3K',
        '4LDK', '4DK', '4K',
        '5LDK', '5DK', '5K'
    ]

    for v in valid:
        if layout.find(v) != -1:
            return True

    return False

def filter_listings(listings: List[Dict]) -> tuple:
    """Filter listings and categorize by pass/fail."""
    passing = []
    failing = []

    for listing in listings:
        issues = []

        # Parse values
        price = parse_price(listing.get('price'))
        size = parse_size(listing.get('size'))
        year = parse_year(listing.get('year'))
        walk = parse_walk(listing.get('walk'))
        layout = listing.get('layout', '').strip()

        # Check price
        if price is None:
            issues.append("price unknown")
        elif price < CRITERIA['min_price']:
            issues.append(f"price {price//10000}M < 15M")
        elif price > CRITERIA['max_price']:
            issues.append(f"price {price//10000}M > 40M")

        # Check size
        if size is None:
            issues.append("size unknown")
        elif size < CRITERIA['min_size']:
            issues.append(f"size {size}m² < 30m²")

        # Check year
        if year is None:
            issues.append("year unknown")
        elif year < CRITERIA['min_year']:
            issues.append(f"year {year} < 1982")

        # Check walk
        if walk is None:
            issues.append("walk unknown")
        elif walk > CRITERIA['max_walk']:
            issues.append(f"walk {walk}min > 15min")

        # Check layout
        if not check_layout(layout):
            issues.append(f"layout '{layout}' < 1LDK")

        # Categorize
        if not issues:
            passing.append(listing)
        else:
            listing['issues'] = issues
            failing.append(listing)

    return passing, failing

def main():
    # Load JSON
    json_file = Path("suumo_new_listings_report.json")
    if not json_file.exists():
        print("Error: suumo_new_listings_report.json not found")
        return

    with open(json_file, 'r', encoding='utf-8') as f:
        listings = json.load(f)

    passing, failing = filter_listings(listings)

    # Write to text file with safe encoding
    report_file = Path("suumo_filter_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"SUUMO NEW LISTINGS FILTER REPORT\n")
        f.write(f"{'='*100}\n\n")

        f.write(f"QUALIFYING LISTINGS: {len(passing)}\n")
        f.write(f"{'-'*100}\n")
        for i, listing in enumerate(passing, 1):
            name = listing.get('name', 'N/A')
            price = listing.get('price', 'N/A')
            size = listing.get('size', 'N/A')
            floor = listing.get('floor', 'N/A')
            year = listing.get('year', 'N/A')
            walk = listing.get('walk', 'N/A')
            station = listing.get('station', 'N/A')
            layout = listing.get('layout', 'N/A')
            f.write(f"{i}. {name} | {price} | {size}m² | {floor}F | {year} | {walk}min ({station}) | {layout}\n")

        f.write(f"\n\nDISQUALIFYING LISTINGS: {len(failing)} (first 30)\n")
        f.write(f"{'-'*100}\n")
        for i, listing in enumerate(failing[:30], 1):
            name = listing.get('name', 'N/A')
            issues = ', '.join(listing.get('issues', []))
            f.write(f"{i}. {name}\n   Issues: {issues}\n")

    # Save passing listings as JSON
    output_file = Path("suumo_qualifying_listings.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(passing, f, ensure_ascii=False, indent=2)

    print(f"Filtering complete!")
    print(f"Found {len(passing)} QUALIFYING listings from 75 new listings")
    print(f"Reports saved to {report_file} and {output_file}")

if __name__ == "__main__":
    main()
