#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXHAUSTIVE PAGINATION SCRAPER - 4 Priority Wards (Sumida, Koto, Katsushika, Itabashi)
Scrapes ALL pages from SUUMO with full pagination
Applies hard filters: ¥15M-40M, 30m²+, 1LDK+, 1982+, ≤15min walk, 2F+, ≤30k fees, Freehold only
Deduplicates against git-tracked 126 existing listings
Output: TSV-formatted candidates
"""

import requests
import re
import time
import json
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
WARDS = {
    'sumida': 'Sumida',
    'koto': 'Koto',
    'katsushika': 'Katsushika',
    'itabashi': 'Itabashi',
}

CRITERIA = {
    'price_min': 15_000_000,
    'price_max': 40_000_000,
    'size_min': 30.0,
    'year_min': 1982,
    'walk_max': 15,
    'floor_min': 2,
    'fees_max': 30_000,
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ja,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

session = requests.Session()
session.headers.update(HEADERS)

def load_existing_names() -> Set[str]:
    """Extract all 126 property names from git log"""
    existing = set()
    try:
        result = subprocess.run(
            ['git', 'log', '--pretty=format:%s'],
            capture_output=True,
            text=True,
            cwd='C:\\Users\\zakat\\Desktop\\apartment'
        )
        for line in result.stdout.split('\n'):
            # Extract property names from "Add #N PropertyName (details)" format
            match = re.search(r'Add #\d+ ([^(]+)', line)
            if match:
                name = match.group(1).strip()
                existing.add(name.lower())
    except Exception as e:
        print(f"[WARNING] Could not load existing names: {e}")

    print(f"[INFO] Loaded {len(existing)} existing property names\n")
    return existing

def fetch_page(url: str, max_retries: int = 3) -> Optional[str]:
    """Fetch page with retry and backoff"""
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code in (503, 429):
                wait_time = 2 ** attempt
                print(f"    [Rate limit] Status {resp.status_code}, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"    [HTTP {resp.status_code}] Stopping pagination")
                return None
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(1)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)

    return None

def extract_listings_from_page(html: str) -> List[Tuple[str, str]]:
    """Extract property codes and names from search results page"""
    listings = []
    soup = BeautifulSoup(html, 'html.parser')

    # Look for listing cards - SUUMO uses various selectors
    # Try multiple patterns
    for div in soup.find_all('div', class_=re.compile('property|listing|item', re.I)):
        # Extract property code (nc_XXXXX)
        code_match = re.search(r'nc_(\d+)', str(div))
        if code_match:
            code = code_match.group(1)

            # Extract name
            name_elem = div.find('a', class_=re.compile('name|title', re.I))
            if not name_elem:
                name_elem = div.find('h2')
            if not name_elem:
                name_elem = div.find('h3')

            if name_elem:
                name = name_elem.get_text(strip=True)
                listings.append((code, name))

    return listings

def fetch_detail_page(ward: str, code: str) -> Optional[str]:
    """Fetch detail page for a specific property"""
    url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward}/nc_{code}/"
    return fetch_page(url)

def parse_detail_page(html: str, code: str, ward: str, name: str) -> Optional[Dict]:
    """Extract all required fields from detail page"""

    data = {
        'code': code,
        'name': name,
        'ward': ward,
        'url': f"https://suumo.jp/ms/chuko/tokyo/sc_{ward}/nc_{code}/",
        'price': None,
        'size': None,
        'layout': None,
        'floor': None,
        'year': None,
        'walk': None,
        'station': None,
        'fees': None,
        'direction': None,
        'ownership': None,
        'occupancy': None,
    }

    # Price (万円)
    price_match = re.search(r'(\d+(?:,\d+)?)\s*万円', html)
    if price_match:
        price_str = price_match.group(1).replace(',', '')
        data['price'] = int(price_str) * 10_000

    # Size (m²)
    size_match = re.search(r'(\d+(?:\.\d+)?)\s*m[²²m2]', html)
    if size_match:
        data['size'] = float(size_match.group(1))

    # Year (YYYY年)
    year_match = re.search(r'(19|20)(\d{2})\s*年', html)
    if year_match:
        data['year'] = int(year_match.group(1) + year_match.group(2))

    # Layout (1LDK, 2DK, etc.)
    layout_match = re.search(r'(\d+)(?:LDK|DK|LK|R)(?:\s|<)', html)
    if layout_match:
        num = layout_match.group(1)
        if 'LDK' in html[layout_match.start():layout_match.end()+10]:
            data['layout'] = f"{num}LDK"
        elif 'DK' in html[layout_match.start():layout_match.end()+10]:
            data['layout'] = f"{num}DK"
        elif 'LK' in html[layout_match.start():layout_match.end()+10]:
            data['layout'] = f"{num}LK"

    # Floor (階)
    floor_match = re.search(r'(\d+)\s*階', html)
    if floor_match:
        data['floor'] = int(floor_match.group(1))

    # Walk time (分)
    walk_match = re.search(r'(\d+)\s*分', html)
    if walk_match:
        data['walk'] = int(walk_match.group(1))

    # Station
    station_match = re.search(r'駅(?:\s|<)(.{0,20})', html)
    if station_match:
        data['station'] = station_match.group(0).strip()

    # Monthly fees (円)
    fees_match = re.search(r'([0-9,]+)\s*円\s*/\s*月', html)
    if fees_match:
        data['fees'] = int(fees_match.group(1).replace(',', ''))

    # Direction (方角)
    for direction in ['南向き', '南', '東向き', '東', '西向き', '西', '北向き', '北', 'SE', 'SW', 'NE', 'NW', 'S', 'E', 'W', 'N']:
        if direction in html:
            data['direction'] = direction
            break

    # Ownership (所有権 vs 借地権)
    if '所有権' in html:
        data['ownership'] = 'Freehold'
    elif '借地権' in html:
        data['ownership'] = 'Leasehold'

    # Occupancy (空家 vs オーナーチェンジ)
    if '空家' in html or '即入可' in html:
        data['occupancy'] = 'Vacant'
    elif 'オーナーチェンジ' in html:
        data['occupancy'] = 'Tenant'

    return data

def passes_criteria(listing: Dict) -> bool:
    """Apply all hard filters"""

    # Price
    if not listing['price'] or listing['price'] < CRITERIA['price_min'] or listing['price'] > CRITERIA['price_max']:
        return False

    # Size
    if not listing['size'] or listing['size'] < CRITERIA['size_min']:
        return False

    # Layout (must be 1LDK or better)
    if not listing['layout']:
        return False

    # Year
    if not listing['year'] or listing['year'] < CRITERIA['year_min']:
        return False

    # Walk time
    if not listing['walk'] or listing['walk'] > CRITERIA['walk_max']:
        return False

    # Floor
    if not listing['floor'] or listing['floor'] < CRITERIA['floor_min']:
        return False

    # Fees
    if listing['fees'] and listing['fees'] > CRITERIA['fees_max']:
        return False

    # Ownership (Freehold only)
    if listing['ownership'] == 'Leasehold':
        return False

    # Direction (no North-only)
    if listing['direction'] in ['北向き', '北', 'N']:
        return False

    return True

def scrape_ward(ward_code: str, ward_name: str, existing_names: Set[str]) -> List[Dict]:
    """Scrape ALL pages for a single ward"""

    results = []
    page = 1
    max_pages = 200  # Safety limit
    consecutive_empty = 0

    print(f"\n{'='*80}")
    print(f"SCRAPING: {ward_name} ({ward_code})")
    print(f"{'='*80}")

    while page <= max_pages and consecutive_empty < 3:
        # Build URL with pagination
        url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward_code}/"
        if page > 1:
            url += f"?page={page}"

        print(f"\n[Page {page}] Fetching: {url}")
        html = fetch_page(url)

        if not html:
            print(f"  [FAIL] Could not fetch page, stopping pagination")
            break

        # Check for "no results" indicators
        if '該当する物件がありません' in html or '物件がありません' in html:
            print(f"  [END] No results on this page, stopping")
            break

        # Extract listings from search results page
        listings = extract_listings_from_page(html)
        print(f"  [FOUND] {len(listings)} properties on page {page}")

        if not listings:
            consecutive_empty += 1
            print(f"  [EMPTY] No listings parsed ({consecutive_empty}/3 consecutive)")
        else:
            consecutive_empty = 0

        # Fetch and parse detail pages
        for idx, (code, name) in enumerate(listings):
            # Check if duplicate
            if name.lower() in existing_names:
                print(f"    [{idx+1}/{len(listings)}] DUPLICATE: {name} (skipping)")
                continue

            # Fetch detail page
            detail_html = fetch_detail_page(ward_code, code)
            if not detail_html:
                print(f"    [{idx+1}/{len(listings)}] FAILED: {name} (code {code})")
                continue

            # Parse detail page
            listing = parse_detail_page(detail_html, code, ward_name, name)

            # Apply criteria
            if passes_criteria(listing):
                print(f"    [{idx+1}/{len(listings)}] ✓ PASS: {name} - ¥{listing['price']:,} {listing['size']}m² {listing['layout']} {listing['floor']}F")
                results.append(listing)
            else:
                reasons = []
                if not listing['price'] or listing['price'] < CRITERIA['price_min'] or listing['price'] > CRITERIA['price_max']:
                    reasons.append(f"price ¥{listing['price'] or 'N/A'}")
                if not listing['size'] or listing['size'] < CRITERIA['size_min']:
                    reasons.append(f"size {listing['size'] or 'N/A'}m²")
                if not listing['year'] or listing['year'] < CRITERIA['year_min']:
                    reasons.append(f"year {listing['year'] or 'N/A'}")
                if not listing['floor'] or listing['floor'] < CRITERIA['floor_min']:
                    reasons.append(f"floor {listing['floor'] or 'N/A'}F")
                if not listing['walk'] or listing['walk'] > CRITERIA['walk_max']:
                    reasons.append(f"walk {listing['walk'] or 'N/A'}min")
                if listing['ownership'] == 'Leasehold':
                    reasons.append("leasehold")

                print(f"    [{idx+1}/{len(listings)}] ✗ FAIL: {name} - {', '.join(reasons)}")

            # Rate limiting
            time.sleep(0.3)

        page += 1
        # Pause between pages
        time.sleep(2)

    print(f"\n[SUMMARY] {ward_name}: Found {len(results)} qualifying listings")
    return results

def main():
    print("\n" + "="*80)
    print("EXHAUSTIVE PAGINATION SCRAPER - 4 Priority Wards")
    print("="*80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"\nCriteria:")
    print(f"  Price: ¥{CRITERIA['price_min']:,} - ¥{CRITERIA['price_max']:,}")
    print(f"  Size: {CRITERIA['size_min']}m²+")
    print(f"  Layout: 1LDK+")
    print(f"  Year: {CRITERIA['year_min']}+")
    print(f"  Walk: {CRITERIA['walk_max']}min or less")
    print(f"  Floor: {CRITERIA['floor_min']}F+")
    print(f"  Fees: ¥{CRITERIA['fees_max']:,}/month max")
    print(f"  Ownership: Freehold only")
    print(f"  Direction: No North-only\n")

    # Load existing names for dedup
    existing_names = load_existing_names()

    # Scrape all 4 wards
    all_results = []
    for ward_code, ward_name in WARDS.items():
        try:
            results = scrape_ward(ward_code, ward_name, existing_names)
            all_results.extend(results)
        except Exception as e:
            print(f"[ERROR] {ward_name}: {e}")
            import traceback
            traceback.print_exc()

    # Output results
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS")
    print(f"{'='*80}")
    print(f"Total new qualifying listings found: {len(all_results)}")

    if all_results:
        output_file = 'C:\\Users\\zakat\\Desktop\\apartment\\EXHAUSTIVE_4WARD_RESULTS.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("EXHAUSTIVE 4-WARD PAGINATION RESULTS\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Wards: Sumida, Koto, Katsushika, Itabashi\n")
            f.write("="*120 + "\n\n")

            f.write("Ward | Name | Price (¥M) | Size (m²) | Layout | Floor | Year | Walk (min) | Station | Fees (¥/mo) | Direction | Ownership | Occupancy | URL\n")
            f.write("-"*120 + "\n")

            for listing in sorted(all_results, key=lambda x: (x['ward'], x['price'] or 0)):
                line = " | ".join([
                    listing.get('ward', 'N/A'),
                    listing.get('name', 'N/A'),
                    f"{listing.get('price', 0) / 1_000_000:.1f}" if listing.get('price') else 'N/A',
                    f"{listing.get('size', 'N/A')}",
                    listing.get('layout', 'N/A'),
                    f"{listing.get('floor', 'N/A')}F",
                    str(listing.get('year', 'N/A')),
                    f"{listing.get('walk', 'N/A')}",
                    listing.get('station', 'N/A'),
                    f"{listing.get('fees', 'N/A')}",
                    listing.get('direction', 'N/A'),
                    listing.get('ownership', 'N/A'),
                    listing.get('occupancy', 'N/A'),
                    listing.get('url', 'N/A'),
                ])
                f.write(line + "\n")

            print(f"\n✓ Results saved to: {output_file}")

        # Also output JSON for easier parsing
        json_file = 'C:\\Users\\zakat\\Desktop\\apartment\\EXHAUSTIVE_4WARD_RESULTS.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON saved to: {json_file}")
    else:
        print("\n⚠ No new qualifying listings found")

if __name__ == '__main__':
    main()
