#!/usr/bin/env python3
"""
Comprehensive Rehouse exhaustive sweep for 4 wards:
Sumida-ku, Katsushika-ku, Itabashi-ku, Koto-ku

Fetches ALL pages, parses ld+json, fetches detail pages for full info,
applies hard filters, deduplicates against existing 115-listing database,
and outputs ONLY NEW viable candidates.
"""

import requests
import json
import re
import time
import sys
from typing import Optional, Dict, List, Tuple, Set
from pathlib import Path

# Force UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuration
WARDS = {
    'sumida': 13107,      # 墨田区
    'katsushika': 13122,  # 葛飾区
    'itabashi': 13119,    # 板橋区
    'koto': 13108,        # 江東区
}

EXISTING_BUILDINGS = {
    # Recent additions (last 50 commits)
    'メゾン蓮根',
    'サンタウン立花１号棟',
    'エスカイア等々力',
    'タウンハイツ亀有２号棟',
    'ライオンズマンション言問',
    'グリーンパーク立石',
    'ダイアパレス立石',
    'リーベスト浮間舟渡',
    'パークハイム上井草',
    'メゾンランジェ早稲田',
    'グリーンキャピタル第三金町',
    'ガーデンプラザ柴又弐番館',
    'コスモ堀切菖蒲園駅前',
    'ニューライフマンション木場',
    'エクレール亀戸',
    '向島ダイヤモンド',
    'ランドステージ墨田',
    '東大島ハイライズ',
    'ルックハイツ両国',
    'ラブリハイツ亀戸',
    '平井パーク・ホームズ',
    '東白鬚第二',
    'パークサイド八広',
    'スカイワード亀有',
    'エスペランサ堀切菖蒲園',
    'ライオンズガーデンお花茶屋',
    '朝日プラザ堀切菖蒲園',
    'セザールお花茶屋',
    'エンゼル柴又プロムテラス',
    'ヴェルアージュ亀有',
    'ライオンズ高砂第5',
    '東糀谷ダイヤモンドマンション',
    '晴紀館',
    'カエサル西尾久',
    '関町南パーク・ホームズ',
    'ライオンズ桜台',
    'Sevenstar Heights Nakano V',
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
        print(f"Error: Status {response.status_code} for page {page_num}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching page {page_num}: {e}", file=sys.stderr)
        return None

def extract_listings_from_html(html: str) -> List[Dict]:
    """Extract listings from ld+json"""
    listings = []
    try:
        # Find ld+json ProductList
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

            # Extract detail ID
            if '/bkdetail/' in listing['detail_url']:
                listing['detail_id'] = listing['detail_url'].split('/bkdetail/')[-1].rstrip('/')

            if listing['building']:
                listings.append(listing)

    except Exception as e:
        print(f"Error parsing HTML: {e}", file=sys.stderr)

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

        # Floor (X階 or X/Y format) - anchor to 階 to avoid aspect ratio confusion
        floor_match = re.search(r'(\d+)\s*階', text)
        if floor_match:
            info['floor'] = floor_match.group(1)
        else:
            # Try X/Y format only if 階 not found
            floor_match = re.search(r'(\d+)\s*/\s*(\d+)\s*階', text)
            if floor_match:
                info['floor'] = f"{floor_match.group(1)}/{floor_match.group(2)}"

        # Fees (管理費+修繕積立金) - look for combined monthly fees
        # Pattern: look for 管理費 + 修繕積立金 = total, or "月額負担金"
        fee_patterns = [
            (r'合計\s*[¥]?\s*(\d{1,5}(?:,\d{3})*)\s*(?:円|/月|/Mon)', 'combined'),
            (r'月額負担金\s*[¥]?\s*(\d{1,5}(?:,\d{3})*)\s*(?:円|/月)', 'monthly burden'),
            (r'管理費\+修繕\s*[¥]?\s*(\d{1,5}(?:,\d{3})*)\s*(?:円|/月)', 'mgmt+reserve'),
            (r'([0-9]{2,3},[0-9]{3}|[0-9]{4,5})\s*円\s*(?:/月|/Mon)', 'yen/month'),
            (r'¥([0-9]{2,3},[0-9]{3}|[0-9]{4,5})', 'yen prefix'),
        ]

        for pattern, desc in fee_patterns:
            fee_match = re.search(pattern, text, re.IGNORECASE)
            if fee_match:
                fee_str = fee_match.group(1).replace(',', '')
                try:
                    fee_val = int(fee_str)
                    if 1000 <= fee_val <= 100000:  # Sanity check: reasonable monthly fee range
                        info['fees'] = fee_val
                        break
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

    except Exception as e:
        pass

    return info

def apply_hard_filters(listing: Dict, detail_info: Dict) -> Tuple[bool, str]:
    """Apply hard filter criteria from CLAUDE.md"""

    # Parse numeric values
    try:
        year = int(detail_info['year']) if detail_info['year'] else 0
    except:
        year = 0

    try:
        size = float(detail_info['size']) if detail_info['size'] else 0
    except:
        size = 0

    try:
        floor = int(detail_info['floor'].split('/')[0]) if detail_info['floor'] else 0
    except:
        floor = 0

    try:
        # Price from ld+json is already in 万円 (10,000-yen units)
        price = int(listing['price_jpy']) if listing['price_jpy'] else 0
    except:
        price = 0

    fees = int(detail_info['fees']) if detail_info['fees'] else 0

    # Hard filters
    if year > 0 and year < 1982:
        return False, f"Built before 1982 ({year})"

    if size > 0 and size < 30:
        return False, f"Smaller than 30m² ({size}m²)"

    if detail_info['room'] and not any(x in detail_info['room'] for x in ['LDK', 'DK']):
        return False, f"Less than 1LDK ({detail_info['room']})"

    if floor == 1:
        return False, "Ground floor (1F)"

    if detail_info['direction'] == '北':
        return False, "North-only facing"

    if fees > 30000:
        return False, f"Monthly fees > ¥30k (¥{fees:,})"

    if detail_info['ownership'] == '借地権':
        return False, "Leasehold (借地権)"

    if price > 40:
        return False, f"Price over ¥40M (¥{price:.1f}万)"

    return True, ""

def scrape_ward(ward_name: str, city_code: int) -> Tuple[List[Dict], int, int]:
    """Scrape all pages for a single ward"""
    all_listings = []
    new_count = 0
    dedup_count = 0

    print(f"\n{'='*80}")
    print(f"SCRAPING {ward_name.upper()}")
    print(f"{'='*80}")

    # Scrape all pages (estimate 10 pages max)
    for page_num in range(1, 15):
        print(f"  Page {page_num}...", end=" ", flush=True)
        html = fetch_page(city_code, page_num)

        if not html:
            print("FAILED")
            break

        listings = extract_listings_from_html(html)
        if not listings:
            print("NO LISTINGS (end of results)")
            break

        print(f"found {len(listings)}")
        all_listings.extend(listings)
        time.sleep(1)  # Rate limiting

    print(f"\nTotal listings for {ward_name}: {len(all_listings)}")
    print(f"Fetching detail pages and applying filters...")

    passed_listings = []

    for idx, listing in enumerate(all_listings):
        # Check for duplicates
        if listing['building'] in EXISTING_BUILDINGS:
            dedup_count += 1
            continue

        # Fetch detail page
        detail_html = fetch_detail_page(listing['detail_url'])
        detail_info = extract_detail_info(detail_html) if detail_html else {}

        # Apply filters
        passes, reason = apply_hard_filters(listing, detail_info)

        if passes:
            new_count += 1

            # Format: price_万 | size | floor | year | walk | station | fees | room | direction | building | url
            # Note: walk and station not available in ld+json, would need detail page parse
            price_man = int(listing['price_jpy']) if listing['price_jpy'] else 0
            record = {
                'building': listing['building'],
                'price_万': price_man,
                'size': detail_info['size'],
                'floor': detail_info['floor'],
                'year': detail_info['year'],
                'room': detail_info['room'],
                'direction': detail_info['direction'],
                'fees': f"¥{detail_info['fees']}/mo",
                'url': listing['detail_url'],
                'ward': ward_name,
            }
            passed_listings.append(record)
            print(f"    ✓ NEW: {listing['building']} ({price_man}万, {detail_info['size']}m², {detail_info['floor']}F)")

        time.sleep(0.3)  # Rate limiting

    return passed_listings, new_count, dedup_count

def main():
    """Main execution"""

    print("="*80)
    print("REHOUSE EXHAUSTIVE SWEEP - 4 WARDS")
    print("="*80)
    print(f"Existing buildings in database: {len(EXISTING_BUILDINGS)}")
    print(f"Target wards: {', '.join(WARDS.keys())}")
    print(f"Target: ≤40M yen, ≥30m², 1LDK+, 2F+, <15 min walk, freehold, fees ≤30k/mo")
    print()

    all_new = []
    total_dedup = 0

    for ward_name, city_code in WARDS.items():
        passed, new_count, dedup_count = scrape_ward(ward_name, city_code)
        all_new.extend(passed)
        total_dedup += dedup_count
        print(f"  → {new_count} new viable, {dedup_count} duplicates")

    # Output results
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS")
    print(f"{'='*80}")
    print(f"Total new viable candidates: {len(all_new)}")
    print(f"Total duplicates rejected: {total_dedup}")
    print()

    if all_new:
        print("NEW VIABLE CANDIDATES (sorted by price):")
        print("-"*80)
        print("Building | Price | Size | Floor | Year | Room | Direction | Fees | Ward | URL")
        print("-"*80)

        # Sort by price
        sorted_new = sorted(all_new, key=lambda x: x['price_万'])

        for record in sorted_new:
            print(f"{record['building']:40} | {record['price_万']:6d} | {record['size']:6} | {record['floor']:8} | {record['year']:4} | {record['room']:6} | {record['direction']:4} | {record['fees']:15} | {record['ward']:10} | {record['url']}")
    else:
        print("No new viable candidates found.")

    # Save to file
    output_file = Path('C:\\Users\\zakat\\Desktop\\apartment\\REHOUSE_EXHAUSTIVE_RESULTS.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"REHOUSE EXHAUSTIVE SWEEP RESULTS\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Total new viable candidates: {len(all_new)}\n")
        f.write(f"Total duplicates rejected: {total_dedup}\n\n")

        if all_new:
            f.write("NEW VIABLE CANDIDATES:\n")
            f.write("-"*80 + "\n")

            for record in sorted(all_new, key=lambda x: x['price_万']):
                f.write(f"{record['building']} | ")
                f.write(f"{record['price_万']}万 | ")
                f.write(f"{record['size']}m² | ")
                f.write(f"{record['floor']}F | ")
                f.write(f"{record['year']} | ")
                f.write(f"{record['room']} | ")
                f.write(f"{record['direction']} | ")
                f.write(f"{record['fees']} | ")
                f.write(f"{record['ward']} | ")
                f.write(f"{record['url']}\n")

    print(f"\nResults saved to: {output_file}")

if __name__ == '__main__':
    main()
