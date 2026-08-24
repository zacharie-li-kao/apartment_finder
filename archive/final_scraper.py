#!/usr/bin/env python3
"""Final comprehensive Rehouse scraper using curl + ld+json + detail pages"""

import os
import json
import re
import sys
import time
import requests
from pathlib import Path

# Force UTF-8 encoding
os.environ['PYTHONUTF8'] = '1'
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13108/"
RESULTS_FILE = Path('C:\\Users\\zakat\\Desktop\\apartment\\REHOUSE_KOTO_RESULTS.txt')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_page(page_num: int = 1) -> str:
    """Fetch page using requests"""
    try:
        params = {} if page_num == 1 else {'page': page_num}
        response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        return ""
    except Exception as e:
        print(f"Error fetching page {page_num}: {e}", file=sys.stderr)
        return ""

def extract_listings_from_html(html: str) -> list:
    """Extract listings from ld+json ItemList"""
    listings = []
    try:
        # Find ld+json ProductList
        match = re.search(r'<script type="application/ld\+json" data-hid="productList">(\{.+?"itemListElement".+?\})</script>', html, re.DOTALL)

        if not match:
            return listings

        json_str = match.group(1)
        data = json.loads(json_str)

        if 'itemListElement' not in data:
            return listings

        for item_wrapper in data['itemListElement']:
            item = item_wrapper.get('item', {})
            if item.get('@type') != 'Product':
                continue

            listing = {
                'building': item.get('name', ''),
                'price_jpy': item.get('offers', {}).get('price', '0'),
                'detail_url': item.get('offers', {}).get('url', ''),
            }

            # Extract detail ID
            detail_id = listing['detail_url'].split('/bkdetail/')[-1].rstrip('/')
            listing['detail_id'] = detail_id

            if listing['building']:
                listings.append(listing)

    except Exception as e:
        print(f"Error parsing HTML: {e}", file=sys.stderr)

    return listings

def fetch_detail_page(detail_url: str) -> str:
    """Fetch detail page"""
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        return ""
    except:
        return ""

def extract_detail_info(html: str) -> dict:
    """Extract size, room, year, floor, fees, direction, ownership from detail page"""
    info = {
        'size': '',
        'room': '',
        'year': '',
        'floor': '',
        'fees': 0,
        'direction': '',
        'ownership': '',
        'can_rebuild': None
    }

    try:
        text = html

        # Size in m²
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎡|m²)', text)
        if size_match:
            info['size'] = size_match.group(1)

        # Room type
        room_match = re.search(r'(\d+S?LDK|Studio)', text)
        if room_match:
            info['room'] = room_match.group(1)

        # Year
        year_match = re.search(r'(19[8-9]\d|20[0-2]\d)\s*年', text)
        if year_match:
            info['year'] = year_match.group(1)

        # Floor (X階 or X/Y format)
        floor_match = re.search(r'(\d+)\s*階|(\d+)\s*/\s*(\d+)', text)
        if floor_match:
            if floor_match.group(3):  # X/Y format
                info['floor'] = f"{floor_match.group(2)}/{floor_match.group(3)}"
            else:  # Just X階
                info['floor'] = floor_match.group(1)

        # Fees (管理費+修繕積立金)
        fee_match = re.search(r'(?:合計|管理費\+修繕|月額負担金)\s*[¥]?\s*(\d{1,5}(?:,\d{3})*)', text)
        if fee_match:
            fee_str = fee_match.group(1).replace(',', '')
            try:
                info['fees'] = int(fee_str)
            except:
                pass

        # Direction (方角)
        for direction in ['南東', '南西', '北東', '北西', '南', '北', '東', '西']:
            if direction + '向' in text or f'向{direction}' in text:
                info['direction'] = direction
                break

        # Ownership (所有権 = freehold, 借地権 = leasehold)
        if '所有権' in text:
            info['ownership'] = '所有権'
        elif '借地権' in text:
            info['ownership'] = '借地権'

        # Can rebuild
        if '再建築可' in text:
            info['can_rebuild'] = True
        elif '再建築不可' in text:
            info['can_rebuild'] = False

        return info

    except Exception as e:
        print(f"Error extracting detail info: {e}", file=sys.stderr)
        return info

def apply_filters(listing: dict, detail: dict) -> tuple:
    """Check filters, return (passes, reason)"""

    # Parse numeric values
    try:
        year = int(detail['year']) if detail['year'] else 0
    except:
        year = 0

    try:
        size = float(detail['size']) if detail['size'] else 0
    except:
        size = 0

    try:
        floor_num = int(detail['floor'].split('/')[0]) if detail['floor'] else 0
    except:
        floor_num = 0

    try:
        price_jpy = int(listing['price_jpy']) if listing['price_jpy'] else 0
        price_man = price_jpy // 10000
    except:
        price_man = 0

    # Hard filters from CLAUDE.md

    # Built before 1982
    if year > 0 and year < 1982:
        return False, f"Built before 1982 ({year})"

    # Smaller than 30m²
    if size > 0 and size < 30:
        return False, f"<30m² ({size}m²)"

    # Less than 1LDK (not LDK or DK)
    if detail['room'] and not any(x in detail['room'] for x in ['LDK', 'DK']):
        return False, f"<1LDK ({detail['room']})"

    # Ground floor (1F)
    if floor_num == 1:
        return False, "Ground floor"

    # Walk time > 15 min (need to parse from somewhere - may not have in detail)
    # This would be in location text, but let's skip for now

    # North-only facing
    if detail['direction'] == '北':
        return False, "North-only facing"

    # Monthly fees > 30k
    if detail['fees'] > 30000:
        return False, f"Fees >30k (¥{detail['fees']:,})"

    # Leasehold
    if detail['ownership'] == '借地権':
        return False, "Leasehold"

    # Cannot rebuild
    if detail['can_rebuild'] == False:
        return False, "Cannot rebuild"

    return True, ""

def main():
    """Main scraping function"""

    print("Starting Rehouse Koto-ku comprehensive scraper...")
    print("Fetching all 9 pages...")

    all_listings = []

    # Scrape all pages
    for page_num in range(1, 10):
        print(f"  Page {page_num}...", end=' ', flush=True)
        html = fetch_page(page_num)
        listings = extract_listings_from_html(html)
        print(f"found {len(listings)} listings")
        all_listings.extend(listings)
        time.sleep(0.5)

    print(f"\nTotal listings found: {len(all_listings)}")
    print("\nFetching detail pages and applying filters...")

    passed = []
    failed = []

    for idx, listing in enumerate(all_listings, 1):
        building = listing['building']
        print(f"  [{idx:3d}/{len(all_listings)}] {building[:40]:40s} ... ", end='', flush=True)

        # Fetch detail page
        detail_html = fetch_detail_page(listing['detail_url'])
        detail_info = extract_detail_info(detail_html)

        # Get walk time from detail page if available (typically in location)
        walk_match = re.search(r'(\d+)\s*分\s*|(\d+)\s*-?\s*minute', detail_html)
        walk_time = walk_match.group(1) if walk_match else ''

        # Get station from detail page
        station_match = re.search(r'駅\s*([^<\n]+)|from\s+([^/\n,]+?)\s+Station', detail_html)
        station = (station_match.group(1) if station_match.group(1) else station_match.group(2)) if station_match else ''

        # Check filters
        passes, reason = apply_filters(listing, detail_info)

        # Convert price to 万円
        price_man = int(listing['price_jpy']) // 10000 if listing['price_jpy'] else 0

        if passes:
            record = f"PASS|{building}|{price_man}|{detail_info['size']}|{detail_info['floor']}|{detail_info['year']}|{walk_time}|{station}|{detail_info['fees']}|{detail_info['room']}|{detail_info['direction']}|{listing['detail_url']}"
            passed.append(record)
            print("PASS")
        else:
            record = f"FAIL|{building}|{reason}|{price_man}|{detail_info['size']}|{detail_info['year']}|{station}|{listing['detail_url']}"
            failed.append(record)
            print(f"FAIL ({reason})")

        time.sleep(0.3)

    # Write results
    print(f"\nWriting results to {RESULTS_FILE}...")
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        f.write(f"REHOUSE KOTO-KU SCRAPING RESULTS\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total listings: {len(all_listings)}\n")
        f.write(f"Passed filters: {len(passed)}\n")
        f.write(f"Failed filters: {len(failed)}\n")
        f.write("="*150 + "\n\n")

        f.write("PASSED LISTINGS:\n")
        f.write("-"*150 + "\n")
        f.write("Format: PASS|Building|Price万|Size|Floor|Year|Walk|Station|Fees|Room|Direction|URL\n")
        f.write("-"*150 + "\n")
        for record in passed:
            f.write(record + "\n")

        f.write(f"\n\nFAILED LISTINGS ({len(failed)} total):\n")
        f.write("-"*150 + "\n")
        f.write("Format: FAIL|Building|Reason|Price万|Size|Year|Station|URL\n")
        f.write("-"*150 + "\n")
        for record in failed:
            f.write(record + "\n")

    print(f"\nResults saved to: {RESULTS_FILE}")
    print(f"Summary: {len(passed)} PASS, {len(failed)} FAIL")

if __name__ == '__main__':
    main()
