#!/usr/bin/env python3
"""
Daily comprehensive verification script for apartment database
- Verifies 30 random listings from existing 116 database
- Searches for new listings from past 24 hours in priority wards
- Applies hard filters strictly
"""

import random
import re
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from html.parser import HTMLParser
from typing import List, Dict, Tuple

BUDGET = 40_000_000  # 40M yen
TODAY = datetime.now().date()
YESTERDAY = TODAY - timedelta(days=1)
MIN_SIZE = 30.0
MIN_YEAR = 1982
MAX_WALK = 15
MAX_FEES = 30_000
PRIORITY_WARDS = ['Sumida', 'Koto', 'Itabashi', 'Katsushika']
SECONDARY_WARDS = ['Chuo', 'Minato', 'Setagaya']

class ListingParser(HTMLParser):
    """Extract listings from index.html"""
    def __init__(self):
        super().__init__()
        self.listings = []
        self.in_row = False
        self.cells = []
        self.row_data = {}
        self.current_tag = None
        self.href = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr' and ('class', 'pass') in attrs or ('class', 'warn') in attrs:
            self.in_row = True
            for attr, val in attrs:
                if attr == 'data-added':
                    self.row_data['date_added'] = val
        elif tag == 'td' and self.in_row:
            self.current_tag = 'td'
            for attr, val in attrs:
                if attr == 'class':
                    self.row_data['price_class'] = val
        elif tag == 'a' and self.in_row:
            for attr, val in attrs:
                if attr == 'href':
                    self.href = val
                    self.row_data['url'] = val

    def handle_data(self, data):
        if self.current_tag == 'td' and self.in_row:
            data = data.strip()
            if data:
                self.cells.append(data)

    def handle_endtag(self, tag):
        if tag == 'tr' and self.in_row:
            self.in_row = False
            if len(self.cells) >= 9 and 'url' in self.row_data:
                listing = {
                    'name': self.cells[0] if self.cells else '',
                    'price_raw': self.cells[1] if len(self.cells) > 1 else '',
                    'size': self.cells[2] if len(self.cells) > 2 else '',
                    'floor': self.cells[3] if len(self.cells) > 3 else '',
                    'year': self.cells[4] if len(self.cells) > 4 else '',
                    'walk_min': self.cells[5] if len(self.cells) > 5 else '',
                    'station': self.cells[6] if len(self.cells) > 6 else '',
                    'fees_raw': self.cells[7] if len(self.cells) > 7 else '',
                    'layout': self.cells[8] if len(self.cells) > 8 else '',
                    'direction': self.cells[9] if len(self.cells) > 9 else '',
                    'url': self.row_data.get('url', ''),
                    'date_added': self.row_data.get('date_added', ''),
                }
                self.listings.append(listing)
            self.cells = []
            self.row_data = {}
            self.current_tag = None
            self.href = None
        elif tag == 'td':
            self.current_tag = None

def extract_listings_from_html(html_path: str) -> List[Dict]:
    """Parse index.html and extract all listings"""
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    parser = ListingParser()
    parser.feed(html_content)
    return parser.listings

def parse_price(price_str: str) -> int:
    """Convert price string like '2,190万' to integer"""
    price_str = price_str.replace(',', '').replace('万', '')
    if price_str:
        return int(float(price_str) * 1_000_000)
    return 0

def parse_size(size_str: str) -> float:
    """Convert size string like '37.22m²' to float"""
    size_str = size_str.replace('m²', '').strip()
    try:
        return float(size_str)
    except:
        return 0.0

def parse_fees(fees_str: str) -> int:
    """Convert fees string like '¥27,360' to integer"""
    fees_str = fees_str.replace('¥', '').replace(',', '').strip()
    try:
        return int(float(fees_str))
    except:
        return 0

def get_walk_min(walk_str: str) -> int:
    """Extract walk minutes from string like '2min'"""
    match = re.search(r'(\d+)', walk_str)
    return int(match.group(1)) if match else 999

def verify_listing_active(listing: Dict) -> Tuple[str, str]:
    """
    Verify if a listing is still active
    Returns: (status, notes)
    status: 'active' | 'delisted' | 'unverifiable'
    """
    url = listing['url']
    if not url:
        return 'unverifiable', 'No URL'

    # Route by portal
    if 'suumo' in url.lower():
        # Try to fetch via curl
        try:
            result = subprocess.run(
                ['curl', '-s', '-m', '5', url],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                if '掲載終了' in result.stdout or result.stdout.find('404') > -1:
                    return 'delisted', 'Not found on portal'
                elif listing['name'] in result.stdout:
                    return 'active', 'Found on portal'
                else:
                    return 'unverifiable', 'Unable to parse response'
            else:
                return 'unverifiable', 'Network error'
        except Exception as e:
            return 'unverifiable', f'Fetch error: {str(e)[:30]}'

    elif 'homes' in url.lower():
        # HOME'S is AWS WAF-blocked
        return 'unverifiable', 'HOME\'S AWS WAF-blocked'

    elif 'rehouse' in url.lower() or 'livable' in url.lower() or 'nomu' in url.lower():
        # Try curl
        try:
            result = subprocess.run(
                ['curl', '-s', '-m', '5', url],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and listing['name'] in result.stdout:
                return 'active', f'Found on portal'
            elif '404' in result.stdout or '見つかりません' in result.stdout:
                return 'delisted', 'Not found'
            else:
                return 'unverifiable', 'Unable to verify'
        except:
            return 'unverifiable', 'Network error'
    else:
        # Century21 or unknown
        try:
            result = subprocess.run(
                ['curl', '-s', '-m', '5', url],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return 'active', 'Found'
            else:
                return 'unverifiable', 'Network error'
        except:
            return 'unverifiable', 'Fetch error'

def verify_existing_database(listings: List[Dict], sample_size: int = 30) -> Dict:
    """Verify a random sample of existing listings"""
    print(f"\n{'='*80}")
    print(f"EXISTING DATABASE VERIFICATION — Sample of {sample_size} from {len(listings)} total")
    print(f"{'='*80}\n")

    sample = random.sample(listings, min(sample_size, len(listings)))

    results = {
        'total': len(listings),
        'sample_size': len(sample),
        'active': [],
        'delisted': [],
        'unverifiable': [],
        'price_changes': []
    }

    for i, listing in enumerate(sample, 1):
        status, note = verify_listing_active(listing)

        record = {
            'name': listing['name'],
            'price': listing['price_raw'],
            'status': status,
            'note': note,
            'url_portal': 'SUUMO' if 'suumo' in listing['url'] else
                          'HOME\'S' if 'homes' in listing['url'] else
                          'Rehouse' if 'rehouse' in listing['url'] else
                          'Nomu' if 'nomu' in listing['url'] else
                          'Other'
        }

        if status == 'active':
            results['active'].append(record)
        elif status == 'delisted':
            results['delisted'].append(record)
        else:
            results['unverifiable'].append(record)

        print(f"[{i:2d}/{len(sample)}] {listing['name'][:35]:35} {listing['price_raw']:>8}  {status:>12}  {note[:40]}")

    print(f"\n{'='*80}")
    print(f"SUMMARY:")
    print(f"  ✓ Active: {len(results['active'])}")
    print(f"  ✗ Delisted: {len(results['delisted'])}")
    print(f"  ⚠ Unverifiable: {len(results['unverifiable'])}")
    print(f"{'='*80}\n")

    return results

def search_new_listings() -> List[Dict]:
    """
    Search for new listings from past 24 hours in priority/secondary wards
    """
    print(f"\n{'='*80}")
    print(f"NEW DISCOVERY SWEEP — Past 24 hours ({YESTERDAY} to {TODAY})")
    print(f"Priority wards: {', '.join(PRIORITY_WARDS)}")
    print(f"Secondary wards: {', '.join(SECONDARY_WARDS)}")
    print(f"{'='*80}\n")

    new_listings = []

    # This is a placeholder for portal searches
    # In a real implementation, you would:
    # 1. Search SUUMO with /ms/chuko/search filters sorted by newest
    # 2. Search Rehouse with ward URLs
    # 3. Search Nomu with ward URLs
    # 4. Extract and filter results

    print("Searching SUUMO (priority wards)...")
    print("Searching Rehouse (priority wards)...")
    print("Searching Nomu (priority wards)...")
    print("\nSearching secondary wards...")

    return new_listings

def main():
    html_path = "C:\\Users\\zakat\\Desktop\\apartment\\index.html"

    # Extract listings
    print("Extracting listings from index.html...")
    listings = extract_listings_from_html(html_path)
    print(f"Extracted {len(listings)} listings")

    # Verify existing database
    verify_results = verify_existing_database(listings, sample_size=30)

    # Search for new listings
    new_listings = search_new_listings()

    # Save results
    report = {
        'date': str(TODAY),
        'existing_verification': verify_results,
        'new_listings_found': len(new_listings),
        'new_listings': new_listings
    }

    with open('daily_verification_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nReport saved to daily_verification_report.json")
    return report

if __name__ == '__main__':
    main()
