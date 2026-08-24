#!/usr/bin/env python3
"""
Search SUUMO for new apartment listings matching criteria.
Compares against existing 116 known properties.
"""

import re
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Set

# Existing known listings (extracted from git history)
KNOWN_LISTINGS = {
    "セザール久が原",  # #126
    "メゾン蓮根",  # #125
    "サンタウン立花１号棟",  # #124
    "エスカイア等々力",  # #123
    "タウンハイツ亀有２号棟",  # #122
    "晴紀館",  # #129
    "関町南パーク・ホームズ",  # #127-128
    "ライオンズ桜台",  # #128
    "カエサル西尾久",  # #126 (Arakawa)
    "パークハイム上井草",  # #124 (Suginami)
    "東糀谷ダイヤモンドマンション",  # #123 (Ota)
    "リーベスト浮間舟渡",  # #122 (Itabashi)
    "Sevenstar Heights Nakano V",  # #121
    "グリーンパーク立石",  # #117-120
    "ダイアパレス立石",  # #116
    "コスモ堀切菖蒲園駅前",  # #112
    "ニューライフマンション木場",  # #102
    "エクレール亀戸",  # #101
    "向島ダイヤモンド",  # #96-100
    "ランドステージ",  # #96-100
    "東大島ハイライズ",  # #96-100
    "ルックハイツ両国",  # #96-100
    "ラブリハイツ亀戸",  # #96-100
    "ガーデンプラザ柴又弐番館",  # #94-95
    "スカイワード亀有",  # #94-95
    "平井パーク・ホームズ",  # #91-93
    "東白鬚第二",  # #91-93
    "パークサイド八広",  # #91-93
    "エスペランサ堀切菖蒲園",  # #89-90
    "ライオンズガーデンお花茶屋",  # #89-90
    "朝日プラザ堀切菖蒲園",  # #87-88
    "セザールお花茶屋",  # #87-88
    "エンゼル柴又プロムテラス",  # #84-86
    "ヴェルアージュ亀有",  # #84-86
    "ライオンズ高砂第5",  # #84-86
    "ライオンズマンション言問",  # #83
    "サンデュエルお花茶屋",  # #3
    "ガーデンプラザ柴又弐番館",  # #2
    "グリーンキャピタル第三金町",  # #3
    "ランドステージ墨田ブライトスクエア",  # #1
}

# Ward URLs
WARDS = {
    "sumida": {"url": "https://suumo.jp/ms/chuko/tokyo/sc_sumida/", "name": "Sumida"},
    "koto": {"url": "https://suumo.jp/ms/chuko/tokyo/sc_koto/", "name": "Koto"},
    "itabashi": {"url": "https://suumo.jp/ms/chuko/tokyo/sc_itabashi/", "name": "Itabashi"},
    "katsushika": {"url": "https://suumo.jp/ms/chuko/tokyo/sc_katsushika/", "name": "Katsushika"},
}

def fetch_page(url: str) -> str:
    """Fetch page content via curl with retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "15", url],
                capture_output=True,
                encoding='utf-8',
                errors='ignore',
                timeout=20
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
            if attempt < max_retries - 1:
                time.sleep(5)
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return ""

def extract_listings(html: str) -> List[Dict]:
    """Extract listing data from HTML."""
    listings = []

    # Split by property_unit elements
    property_blocks = re.split(r'<div class="property_unit[^"]*"', html)

    for block in property_blocks[1:]:  # Skip first empty split
        data = {}

        # Extract property name (from dottable-vm dd tag after 物件名)
        name_match = re.search(r'<dt[^>]*>物件名</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
        if name_match:
            data['name'] = name_match.group(1).strip()
        else:
            continue

        # Extract price (from dottable-value span)
        price_match = re.search(r'<span class="dottable-value">([0-9,]+万円)</span>', block)
        if price_match:
            data['price'] = price_match.group(1)

        # Extract size in m²
        size_match = re.search(r'>(\d+\.?\d*)m<sup>2</sup>', block)
        if size_match:
            data['size'] = size_match.group(1)

        # Extract floor
        floor_match = re.search(r'<dd[^>]*>(\d+)F</dd>', block)
        if floor_match:
            data['floor'] = floor_match.group(1)

        # Extract year
        year_match = re.search(r'>([12]\d{3}(?:年\d{1,2}月)?)</dd>', block)
        if year_match:
            data['year'] = year_match.group(1)

        # Extract walk time
        walk_match = re.search(r'徒歩(\d+)分', block)
        if walk_match:
            data['walk'] = walk_match.group(1)

        # Extract station
        station_match = re.search(r'「([^」]+)」徒歩', block)
        if station_match:
            data['station'] = station_match.group(1)

        # Extract layout (from dottable dd)
        layout_match = re.search(r'<dt[^>]*>間取り</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
        if layout_match:
            data['layout'] = layout_match.group(1).strip()

        if data.get('name'):
            listings.append(data)

    return listings

def search_ward(ward_code: str, ward_info: Dict) -> List[Dict]:
    """Search a specific ward and return new listings."""
    print(f"\nSearching {ward_info['name']} ward...")
    url = ward_info['url']

    # Fetch first page
    html = fetch_page(url)
    if not html:
        print(f"  Failed to fetch {ward_info['name']}")
        return []

    # Extract listings from first page
    listings = extract_listings(html)
    print(f"  Found {len(listings)} listings on first page")

    # Filter for new listings only
    new_listings = [l for l in listings if l.get('name') not in KNOWN_LISTINGS]

    return new_listings

def main():
    print(f"SUUMO New Listings Search - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Comparing against {len(KNOWN_LISTINGS)} known listings")
    print("=" * 80)

    all_new = []

    for ward_code, ward_info in WARDS.items():
        new_listings = search_ward(ward_code, ward_info)

        if new_listings:
            print(f"\n  NEW LISTINGS in {ward_info['name']}: {len(new_listings)} found")
            for listing in new_listings[:10]:  # Show first 10
                try:
                    name = listing.get('name', 'N/A')
                    price = listing.get('price', 'N/A')
                    size = listing.get('size', 'N/A')
                    floor = listing.get('floor', 'N/A')
                    year = listing.get('year', 'N/A')
                    walk = listing.get('walk', 'N/A')
                    station = listing.get('station', 'N/A')
                    print(f"    - {name} | {price} | {size}m2 | {floor}F | {year} | {walk}min ({station})")
                except Exception as e:
                    print(f"    - [Error displaying listing: {e}]")
            all_new.extend(new_listings)
        else:
            print(f"\n  No new listings in {ward_info['name']}")

        # Rate limiting
        time.sleep(5)

    print(f"\n{'=' * 80}")
    print(f"Total new listings found: {len(all_new)}")

    return all_new

if __name__ == "__main__":
    new_listings = main()

    # Save results to JSON file
    output_file = Path("suumo_new_listings_report.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(new_listings, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {output_file}")
