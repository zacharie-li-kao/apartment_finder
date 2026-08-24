#!/usr/bin/env python3
"""
COMPREHENSIVE NOMU SCRAPER - PHASE 1 & 2
Scrape all pages across 12 wards, extract detail data, filter by criteria, deduplicate.
Output: Tab-separated results matching all 8 filter criteria.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin
from typing import Dict, List, Tuple
import sys

# Configuration
NOMU_WARDS = {
    'Arakawa': 13118,
    'Chuo': 13102,
    'Itabashi': 13119,
    'Katsushika': 13122,
    'Kita': 13117,
    'Koto': 13108,
    'Minato': 13103,
    'Nakano': 13114,
    'Ota': 13111,
    'Setagaya': 13112,
    'Sumida': 13107,
    'Nerima': 13120,
}

# Filter criteria
PRICE_MIN = 1_500_000
PRICE_MAX = 40_000_000
SIZE_MIN = 30.0
YEAR_MIN = 1982
WALK_MAX = 15
FLOOR_MIN = 2
FEES_MAX = 30_000
NO_NORTH_ONLY = True

# Load existing listings
existing_listings = set()
try:
    with open('existing_listings.txt', 'r', encoding='utf-8') as f:
        existing_listings = set(line.strip() for line in f if line.strip())
    print(f"[INFO] Loaded {len(existing_listings)} existing listings for dedup\n")
except Exception as e:
    print(f"[WARNING] Could not load existing listings: {e}\n")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def extract_price(text: str) -> Tuple[int, str]:
    """Extract price in yen. Returns (int price or 0, formatted string)."""
    try:
        match = re.search(r'(\d+)\s*,?\s*(\d{3})?\s*万円', text)
        if match:
            # 万 = 10,000, so multiply by 10,000
            price_str = match.group(0).replace(',', '').replace('万円', '').strip()
            price_int = int(float(price_str)) * 10_000
            return price_int, match.group(0)
    except:
        pass
    return 0, ''

def extract_size(text: str) -> Tuple[float, str]:
    """Extract size in m². Returns (float, formatted string)."""
    try:
        match = re.search(r'(\d+\.?\d*)\s*m[²²m2]', text)
        if match:
            size_float = float(match.group(1))
            return size_float, match.group(0)
    except:
        pass
    return 0.0, ''

def extract_year(text: str) -> Tuple[int, str]:
    """Extract year built. Returns (int year or 0, formatted string)."""
    try:
        match = re.search(r'(19|20)(\d{2})\s*年', text)
        if match:
            year_int = int(match.group(1) + match.group(2))
            return year_int, match.group(0)
    except:
        pass
    return 0, ''

def extract_walk_time(text: str) -> Tuple[int, str]:
    """Extract walk time in minutes. Returns (int minutes or 0, formatted string)."""
    try:
        match = re.search(r'(\d+)\s*分', text)
        if match:
            walk_int = int(match.group(1))
            return walk_int, match.group(0)
    except:
        pass
    return 0, ''

def extract_station(text: str) -> str:
    """Extract station name."""
    # Look for station patterns
    try:
        matches = re.findall(r'「([^」]+)」\s*駅', text)
        if matches:
            return matches[0]
    except:
        pass
    return ''

def extract_fees(text: str) -> Tuple[int, str]:
    """Extract monthly fees. Returns (int yen or 0, formatted string)."""
    try:
        # Look for various fee patterns
        patterns = [
            r'管理費.*?(\d+),?(\d{3})\s*円',
            r'(\d+),?(\d{3})\s*円/月',
            r'(\d+),?(\d{3})\s*円'
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                fee_str = match.group(0)
                fee_int = int(fee_str.replace(',', '').replace('円/月', '').replace('円', '').strip())
                return fee_int, fee_str
    except:
        pass
    return 0, ''

def extract_floor(text: str) -> str:
    """Extract floor information."""
    try:
        # Look for floor patterns like "3/6" or "15階"
        match = re.search(r'(\d+)\s*[/階]\s*(\d+)?', text)
        if match:
            if match.group(2):
                return f"{match.group(1)}F/{match.group(2)}F"
            return match.group(0)
    except:
        pass
    return ''

def extract_direction(text: str) -> str:
    """Extract direction/orientation."""
    directions = ['南東', '南西', '北東', '北西', '南', '北', '東', '西']
    for direction in directions:
        if direction in text:
            return direction
    return ''

def is_north_only(text: str) -> bool:
    """Check if only north-facing (北向き)."""
    if '北向き' in text or '北のみ' in text:
        return True
    # Check if 南/東/西 are present - if so, not north-only
    if any(d in text for d in ['南', '東', '西']):
        return False
    if '北' in text:
        return True
    return False

def extract_detail_page_data(detail_url: str) -> Dict:
    """Fetch and parse a detail page. Returns dict with all fields."""
    data = {
        'price': 0,
        'price_str': '',
        'size': 0.0,
        'size_str': '',
        'floor': '',
        'year': 0,
        'year_str': '',
        'walk': 0,
        'walk_str': '',
        'station': '',
        'fees': 0,
        'fees_str': '',
        'direction': '',
        'layout': '',
    }

    try:
        resp = session.get(detail_url, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()

        # Extract all fields
        data['price'], data['price_str'] = extract_price(text)
        data['size'], data['size_str'] = extract_size(text)
        data['year'], data['year_str'] = extract_year(text)
        data['walk'], data['walk_str'] = extract_walk_time(text)
        data['station'] = extract_station(text)
        data['fees'], data['fees_str'] = extract_fees(text)
        data['floor'] = extract_floor(text)
        data['direction'] = extract_direction(text)

        # Extract layout (1LDK, 2LDK, etc.)
        layout_match = re.search(r'([1-5])[LDK]+', text)
        if layout_match:
            data['layout'] = layout_match.group(0)

        time.sleep(0.3)  # Rate limit

    except Exception as e:
        pass

    return data

def passes_filters(data: Dict) -> Tuple[bool, List[str]]:
    """Check if listing passes all filter criteria. Returns (passes, reasons)."""
    reasons = []

    if data['price'] < PRICE_MIN:
        reasons.append(f"Price {data['price_str']} < ¥1.5M")
        return False, reasons
    if data['price'] > PRICE_MAX:
        reasons.append(f"Price {data['price_str']} > ¥40M")
        return False, reasons

    if data['size'] < SIZE_MIN:
        reasons.append(f"Size {data['size_str']} < 30m²")
        return False, reasons

    if data['year'] > 0 and data['year'] < YEAR_MIN:
        reasons.append(f"Year {data['year_str']} < 1982")
        return False, reasons

    if data['walk'] > WALK_MAX:
        reasons.append(f"Walk {data['walk_str']} > 15min")
        return False, reasons

    # Floor check - assume minimum floor from string if available
    if data['floor']:
        floor_match = re.search(r'^(\d+)', data['floor'])
        if floor_match:
            floor_num = int(floor_match.group(1))
            if floor_num < FLOOR_MIN:
                reasons.append(f"Floor {data['floor']} < 2F")
                return False, reasons
    else:
        reasons.append("Floor not found")
        return False, reasons

    if data['fees'] > FEES_MAX and data['fees'] > 0:
        reasons.append(f"Fees {data['fees_str']} > ¥30k/month")
        return False, reasons

    if is_north_only(data['direction']):
        reasons.append("North-facing only")
        return False, reasons

    return True, []

def scrape_ward_all_pages(ward_name: str, ward_code: int) -> List[Dict]:
    """Scrape all pages for a ward and extract detail data."""
    results = []
    page = 1
    max_pages = 50  # Safety limit

    print(f"\n{'=' * 80}")
    print(f"WARD: {ward_name} (Code {ward_code})")
    print('=' * 80)

    while page <= max_pages:
        url = f"https://www.nomu.com/mansion/area_tokyo/{ward_code}/?pager_page={page}"

        try:
            print(f"  Page {page}: ", end='', flush=True)
            resp = session.get(url, timeout=10)
            resp.encoding = 'utf-8'

            if resp.status_code != 200:
                print(f"Status {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'/mansion/id/'))

            if not links:
                print("No listings (end of results)")
                break

            page_new_count = 0
            for link in links:
                name = link.get_text(strip=True)
                detail_url = urljoin('https://www.nomu.com', link.get('href', ''))

                # Check if already in database
                if name in existing_listings or not name:
                    continue

                # Fetch detail page
                detail_data = extract_detail_page_data(detail_url)

                # Check filters
                passes, reasons = passes_filters(detail_data)
                if passes:
                    results.append({
                        'name': name,
                        'url': detail_url,
                        'ward': ward_name,
                        **detail_data,
                    })
                    page_new_count += 1

            print(f"Found {page_new_count} qualifying new listings")
            page += 1
            time.sleep(0.5)

        except Exception as e:
            print(f"Error: {e}")
            break

    return results

def format_output(listings: List[Dict]) -> str:
    """Format listings for output."""
    lines = []
    lines.append("NEW LISTINGS FROM NOMU.COM - ALL FILTERS APPLIED")
    lines.append("=" * 150)
    lines.append("Name | Price | Size | Floor | Year | Walk/Station | Fees | Direction | Notes")
    lines.append("=" * 150)
    lines.append("")

    for listing in sorted(listings, key=lambda x: (x['ward'], x['price'])):
        notes = []
        if listing['layout']:
            notes.append(listing['layout'])
        if listing['price'] < 30_000_000:
            notes.append("Below market")

        note_str = " | ".join(notes) if notes else ""

        line = f"{listing['name']} | {listing['price_str']} | {listing['size_str']} | {listing['floor']} | {listing['year_str']} | {listing['station']}{listing['walk_str']} | {listing['fees_str']}/月 | {listing['direction']} | {note_str}"
        lines.append(line)

    return "\n".join(lines)

def main():
    print("\n" + "=" * 80)
    print("COMPREHENSIVE NOMU SCRAPER - ALL 12 WARDS")
    print("Scraping: All pages | Extracting: Full detail data | Filtering: 8 criteria")
    print("=" * 80)

    all_results = []

    for ward_name, ward_code in NOMU_WARDS.items():
        ward_results = scrape_ward_all_pages(ward_name, ward_code)
        all_results.extend(ward_results)

    print("\n" + "=" * 80)
    print(f"FINAL RESULTS: {len(all_results)} NEW qualifying listings found across all wards")
    print("=" * 80)

    # Save results
    output = format_output(all_results)
    with open('FINAL_NEW_LISTINGS.txt', 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\nResults saved to FINAL_NEW_LISTINGS.txt")
    print("\nOutput format:")
    print("Name | Price | Size | Floor | Year | Walk/Station | Fees | Direction | Notes")
    print("\nSample line:")
    if all_results:
        first = all_results[0]
        print(f"{first['name']} | {first['price_str']} | {first['size_str']} | {first['floor']} | {first['year_str']} | {first['station']}{first['walk_str']} | {first['fees_str']}/月 | {first['direction']} |")

if __name__ == '__main__':
    main()
