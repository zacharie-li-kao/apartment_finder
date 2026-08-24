#!/usr/bin/env python3
"""
Extract results for all 246 Rehouse Koto-ku listings
This script will be called repeatedly from the browser extraction
"""

import json
import sys
import re
from datetime import datetime

# Fix encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

RESULTS_FILE = 'C:\\Users\\zakat\\Desktop\\apartment\\koto_listings.jsonl'

def parse_listing_data(raw_text):
    """Parse listing data from raw page text"""
    """
    Expected format from browser get_page_text:
    [Status markers like NEW]
    Building Name
    Price (e.g., 15,490万円 or 152 million yen)
    Address/Location info
    Walk time and station info
    Room type, Size, Year, Floor
    """

    listings = []

    # Split by building names which are typically followed by prices
    # This is a simplified parser - in production would use structured data

    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip non-listing lines
        if any(x in line for x in ['Showing', 'Sort order', 'Save search', 'new properties', 'View details', 'inquiry', 'nearby']):
            i += 1
            continue

        # Detect building name (usually followed by price)
        # Building names are typically 10-50 chars, don't contain typical keywords
        if (len(line) > 3 and len(line) < 60 and
            not any(x in line for x in ['million', 'LDK', 'floor', 'walk', '万', 'Open', 'Renovation'])):

            building = line
            i += 1

            # Try to collect the next fields
            listing_data = {'building': building}

            # Get price (should be next financial figure)
            for _ in range(10):
                if i < len(lines):
                    if any(x in lines[i] for x in ['million', '万']):
                        listing_data['price'] = lines[i]
                        i += 1
                        break
                    i += 1

            listings.append(listing_data)
        else:
            i += 1

    return listings

def append_results(page_num, listings_data):
    """Append listings to results file"""
    with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
        for data in listings_data:
            data['page'] = page_num
            data['timestamp'] = datetime.now().isoformat()
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Called with page data
        page_num = int(sys.argv[1]) if sys.argv[1].isdigit() else 1
        listings_text = sys.argv[2] if len(sys.argv) > 2 else ""

        listings = parse_listing_data(listings_text)
        append_results(page_num, listings)
        print(f"Appended {len(listings)} listings from page {page_num}")
    else:
        print(f"Usage: python extract_rehouse_results.py <page_num> '<text>'")
        print(f"Results file: {RESULTS_FILE}")
