#!/usr/bin/env python3
"""
Diagnostic version of exhaustive sweep - shows WHY listings are rejected
"""

import requests
import json
import re
import sys
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import time

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WARDS = {
    'sumida': 13108,
    'katsushika': 13120,
    'itabashi': 13105,
    'koto': 13109,
}

BASE_URL = "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{city_code}/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_page(city_code: int, page_num: int = 1) -> Optional[str]:
    """Fetch a Rehouse listing page"""
    try:
        url = BASE_URL.format(city_code=city_code)
        params = {} if page_num == 1 else {'page': page_num}
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        return None
    except:
        return None

def extract_listings_from_html(html: str) -> List[Dict]:
    """Extract listings from ld+json"""
    listings = []
    try:
        match = re.search(
            r'<script type="application/ld\+json" data-hid="productList">(\{.+?"itemListElement".+?\})</script>',
            html,
            re.DOTALL
        )

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

            if '/bkdetail/' in listing['detail_url']:
                listing['detail_id'] = listing['detail_url'].split('/bkdetail/')[-1].rstrip('/')

            if listing['building']:
                listings.append(listing)

    except Exception as e:
        pass

    return listings

def fetch_detail_page(detail_url: str) -> Optional[str]:
    """Fetch detail page HTML"""
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=20)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        return None
    except:
        return None

def extract_detail_info(html: str) -> Dict:
    """Extract size, room, year, floor, fees, direction, ownership from detail page"""
    info = {
        'size': '',
        'room': '',
        'year': '',
        'floor': '',
        'fees': 0,
        'direction': '',
        'ownership': '',
        'walk': '',
        'station': '',
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
        year_match = re.search(r'(19[7-9]\d|20[0-2]\d)\s*年', text)
        if year_match:
            info['year'] = year_match.group(1)

        # Floor (X階 or X/Y format)
        floor_match = re.search(r'(\d+)\s*階|(\d+)\s*/\s*(\d+)', text)
        if floor_match:
            if floor_match.group(3):
                info['floor'] = f"{floor_match.group(2)}/{floor_match.group(3)}"
            else:
                info['floor'] = floor_match.group(1)

        # Fees (管理費+修繕積立金)
        fee_match = re.search(r'(?:合計|管理費\+修繕|月額|管理費)\s*[¥]?\s*(\d{1,5}(?:,\d{3})*)\s*(?:円|万)?(?:/月|\/月)', text)
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

        # Walk time
        walk_match = re.search(r'(\d+)\s*(?:分|min)', text)
        if walk_match:
            info['walk'] = walk_match.group(1)

        # Station
        station_match = re.search(r'([ぁ-ん][ぁ-ん0-9]{0,10})(?:駅|station)', text)
        if station_match:
            info['station'] = station_match.group(1)

    except:
        pass

    return info

def filter_summary_sample(ward_name: str, city_code: int, sample_size: int = 20):
    """Fetch first page and show diagnostic info for sample listings"""

    print(f"\nDIAGNOSTIC SAMPLE FOR {ward_name.upper()}")
    print("="*100)

    html = fetch_page(city_code, 1)
    if not html:
        print("Failed to fetch page")
        return

    listings = extract_listings_from_html(html)
    print(f"Found {len(listings)} listings on page 1")
    print()

    for idx, listing in enumerate(listings[:sample_size]):
        print(f"\n{idx+1}. {listing['building'][:50]}")
        print(f"   Price: ¥{listing['price_jpy']}万")
        print(f"   URL: {listing['detail_url'][:70]}...")

        # Fetch detail
        detail_html = fetch_detail_page(listing['detail_url'])
        if not detail_html:
            print("   [Detail page failed to load]")
            time.sleep(0.3)
            continue

        info = extract_detail_info(detail_html)

        # Show extracted info
        print(f"   Extracted: {info['size']}m² | {info['room']} | {info['year']} | {info['floor']}F | ¥{info['fees']}/mo | {info['direction']}向 | {info['ownership']}")

        # Check filters and explain
        filters_ok = []
        filters_fail = []

        try:
            year = int(info['year']) if info['year'] else 0
            price = int(listing['price_jpy']) if listing['price_jpy'] else 0
            size = float(info['size']) if info['size'] else 0
            floor = int(info['floor'].split('/')[0]) if info['floor'] else 0
            fees = int(info['fees']) if info['fees'] else 0

            if year > 0 and year >= 1982:
                filters_ok.append("✓ Built 1982+")
            else:
                filters_fail.append(f"✗ Pre-1982 ({year})" if year else "✗ Year unknown")

            if size > 0 and size >= 30:
                filters_ok.append(f"✓ Size {size}m² ≥30")
            else:
                filters_fail.append(f"✗ Size {size}m² <30" if size else "✗ Size unknown")

            if info['room'] and any(x in info['room'] for x in ['LDK', 'DK']):
                filters_ok.append(f"✓ Layout {info['room']}")
            else:
                filters_fail.append(f"✗ Layout {info['room']} <1LDK" if info['room'] else "✗ Layout unknown")

            if floor > 1:
                filters_ok.append(f"✓ Floor {floor}F ≥2")
            elif floor == 1:
                filters_fail.append("✗ Ground floor (1F)")
            else:
                filters_fail.append("✗ Floor unknown")

            if info['direction'] != '北':
                filters_ok.append(f"✓ Direction {info['direction'] or 'unknown'}向")
            else:
                filters_fail.append("✗ North-only facing")

            if fees <= 30000:
                filters_ok.append(f"✓ Fees ¥{fees}/mo ≤30k")
            else:
                filters_fail.append(f"✗ Fees ¥{fees}/mo >30k")

            if info['ownership'] != '借地権':
                filters_ok.append(f"✓ {info['ownership'] or 'Ownership TBD'}")
            else:
                filters_fail.append("✗ Leasehold")

            if price <= 40000:
                filters_ok.append(f"✓ Price {price}万 ≤40M")
            else:
                filters_fail.append(f"✗ Price {price}万 >40M")

        except Exception as e:
            filters_fail.append(f"Error: {e}")

        print(f"   Filters: {' | '.join(filters_ok)}")
        if filters_fail:
            print(f"   BLOCKED: {' | '.join(filters_fail)}")

        time.sleep(0.3)

if __name__ == '__main__':
    print("REHOUSE DIAGNOSTIC SWEEP - FILTER ANALYSIS")
    print("="*100)
    print("Showing first 20 listings per ward to diagnose why passes/failures occur\n")

    for ward_name, city_code in WARDS.items():
        filter_summary_sample(ward_name, city_code, sample_size=20)

    print("\n" + "="*100)
    print("END OF DIAGNOSTIC REPORT")
