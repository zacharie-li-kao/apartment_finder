#!/usr/bin/env python3
"""
Verify 18 specific SUUMO listings by searching and extracting key information.
"""

import requests
import re
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urlencode

# List of 18 buildings to verify
LISTINGS = [
    {"name": "モアステージ隅田", "price": "2380万円", "price_num": 2380},
    {"name": "ビィ・フォルマ亀戸", "price": "3980万円", "price_num": 3980},  # duplicate with #3
    {"name": "ビィ・フォルマ亀戸", "price": "3980万円", "price_num": 3980},  # duplicate with #2
    {"name": "ＮＩＣアーバンハイム亀戸", "price": "3990万円", "price_num": 3990},
    {"name": "サンシャインハイツ", "price": "3290万円", "price_num": 3290},
    {"name": "大島ロイヤルマンション", "price": "3380万円", "price_num": 3380},
    {"name": "ツインシティ壱番館エトランズ東砂", "price": "3490万円", "price_num": 3490},
    {"name": "ツインシティ東砂アネックス", "price": "3980万円", "price_num": 3980},
    {"name": "グリーンパーク第2南綾瀬602号室", "price": "2699万円", "price_num": 2699},
    {"name": "ライオンズマンション柴又", "price": "2980万円", "price_num": 2980},
    {"name": "ネオコーポ金町", "price": "2980万円", "price_num": 2980},
    {"name": "NICアーバンハイム四つ木第２", "price": "3100万円", "price_num": 3100},
    {"name": "ライオンズマンション綾瀬", "price": "3580万円", "price_num": 3580},
    {"name": "GSハイム第二金町", "price": "3790万円", "price_num": 3790},
    {"name": "コスモ西亀有", "price": "3790万円", "price_num": 3790},
    {"name": "新小岩パーク・ホームズ", "price": "3890万円", "price_num": 3890},
    {"name": "ニックハイム渋江公園", "price": "3980万円", "price_num": 3980},
    {"name": "ディナ・スカーラお花茶屋", "price": "3980万円", "price_num": 3980},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def search_building(name, price_num):
    """Search for a building by name and extract its nc code and details."""
    try:
        # Search SUUMO with keyword
        search_url = "https://suumo.jp/jj/common/ichiran/JJ901FC001/"
        params = {
            "kw": name,
            "ar": "030",  # Tokyo
            "bs": "011",  # Used condos
        }

        response = requests.get(search_url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()

        # Parse search results to find matching building
        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for listing links in the search results
        # The nc_ code appears in URLs like /ms/chuko/tokyo/sc_xxx/nc_XXXXX/
        links = soup.find_all('a', href=re.compile(r'/chukomansion/.*nc_\d+'))

        if not links:
            print(f"  No results found for '{name}'")
            return None

        # Extract nc code from the link
        first_link = links[0]
        href = first_link.get('href', '')

        # Extract the nc_ code from the redirect URL
        nc_match = re.search(r'nc_(\d+)', href)
        if not nc_match:
            print(f"  Could not extract nc code from {href}")
            return None

        nc_code = nc_match.group(1)
        print(f"  Found nc code: {nc_code}")

        return nc_code

    except Exception as e:
        print(f"  Error searching for '{name}': {e}")
        return None

def fetch_detail_page(nc_code, ward):
    """Fetch the detail page for a building using the clean URL."""
    try:
        # Try to construct the clean detail URL
        # Format: https://suumo.jp/ms/chuko/tokyo/sc_{ward}/nc_{code}/
        detail_url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward}/nc_{nc_code}/"

        response = requests.get(detail_url, headers=HEADERS, timeout=10)

        if response.status_code == 404:
            # If not found, try fetching from gateway
            # The gateway URL might work if direct URL doesn't
            print(f"    Direct URL returned 404, trying gateway...")
            return None

        response.raise_for_status()
        return response.content

    except Exception as e:
        print(f"    Error fetching detail page: {e}")
        return None

def parse_detail_page(html_content):
    """Extract required information from detail page."""
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract information from the detail page
        # Structure may vary, so we'll look for common patterns

        info = {
            "floor": None,
            "fees": None,
            "ownership": None,
            "direction": None,
            "status": None,
        }

        # Look for floor information (階)
        floor_patterns = [
            r'(\d+)階',
            r'(\d+)F',
            r'(\d+)[階Ｆ]',
        ]

        page_text = soup.get_text()

        for pattern in floor_patterns:
            match = re.search(pattern, page_text)
            if match:
                info["floor"] = int(match.group(1))
                break

        # Look for fees (管理費 + 修繕積立金)
        fees_pattern = r'(?:管理費|修繕積立金|月額料金)[：:]\s*([¥￥])?(\d+(?:,\d+)?)(?:円)?'
        fees_match = re.search(fees_pattern, page_text)
        if fees_match:
            fees_str = fees_match.group(2).replace(',', '')
            info["fees"] = int(fees_str) if fees_str.isdigit() else None

        # Look for ownership type (所有権 vs 借地権)
        if '所有権' in page_text:
            info["ownership"] = "所有権"  # Freehold
        elif '借地権' in page_text:
            info["ownership"] = "借地権"  # Leasehold

        # Look for direction/orientation (方角)
        directions = ['北', '北東', '東', '南東', '南', '南西', '西', '北西']
        for direction in directions:
            if f'{direction}向き' in page_text or f'向き{direction}' in page_text:
                info["direction"] = direction
                break

        # Look for occupancy status (空家 vs 居住中)
        if '空家' in page_text:
            info["status"] = "空家"
        elif '居住中' in page_text or 'オーナーチェンジ' in page_text:
            info["status"] = "居住中"

        return info

    except Exception as e:
        print(f"    Error parsing detail page: {e}")
        return None

def verify_listing(listing):
    """Verify a single listing."""
    name = listing["name"]
    price = listing["price"]

    print(f"\nVerifying: {name} ({price})")

    # Search for the building
    nc_code = search_building(name, listing["price_num"])
    if not nc_code:
        return None

    # Fetch detail page
    # We need to determine the ward - this is a limitation, we'll need to try multiple wards
    # For now, let's try common wards
    wards = ["sumida", "koto", "edogawa", "katsushika", "arakawa"]

    html_content = None
    for ward in wards:
        print(f"    Trying ward: {ward}")
        html_content = fetch_detail_page(nc_code, ward)
        if html_content:
            break

    if not html_content:
        print(f"    Could not fetch detail page for nc_{nc_code}")
        return None

    # Parse detail page
    info = parse_detail_page(html_content)
    return info

def main():
    """Main function to verify all listings."""
    print(f"Verifying {len(LISTINGS)} listings...\n")

    results = []
    for i, listing in enumerate(LISTINGS, 1):
        print(f"[{i}/{len(LISTINGS)}]", end=" ")

        # Skip if duplicate
        if i == 3 and LISTINGS[2]["name"] == LISTINGS[1]["name"]:
            print(f"Skipping duplicate: {listing['name']}")
            results.append({
                "index": i,
                "name": listing["name"],
                "price": listing["price"],
                "floor": None,
                "fees": None,
                "ownership": None,
                "direction": None,
                "status": "DUPLICATE",
                "verdict": "N/A"
            })
            continue

        info = verify_listing(listing)

        if info:
            # Determine pass/fail
            floor_ok = info.get("floor") is not None and info["floor"] >= 2
            fees_ok = info.get("fees") is None or info["fees"] <= 30000
            ownership_ok = info.get("ownership") == "所有権"

            verdict = "✓ PASS" if (floor_ok and fees_ok and ownership_ok) else "✗ FAIL"

            result = {
                "index": i,
                "name": listing["name"],
                "price": listing["price"],
                "floor": info.get("floor"),
                "fees": info.get("fees"),
                "ownership": info.get("ownership"),
                "direction": info.get("direction"),
                "status": info.get("status"),
                "verdict": verdict
            }
        else:
            result = {
                "index": i,
                "name": listing["name"],
                "price": listing["price"],
                "floor": None,
                "fees": None,
                "ownership": None,
                "direction": None,
                "status": "ERROR",
                "verdict": "❌ NO DATA"
            }

        results.append(result)
        time.sleep(1)  # Rate limiting

    # Print results as CSV
    print("\n\n" + "="*100)
    print("RESULTS (CSV):")
    print("="*100)
    print("No. | Name | Price | Floor | Fees/mo | Ownership | Direction | Status | Verdict")
    print("-" * 100)

    for result in results:
        floor_str = str(result["floor"]) + "F" if result["floor"] else "N/A"
        fees_str = f"¥{result['fees']:,}" if result["fees"] else "N/A"
        ownership_str = result["ownership"] or "N/A"
        direction_str = result["direction"] or "N/A"
        status_str = result["status"] or "N/A"

        print(f"{result['index']:2d} | {result['name']:40s} | {result['price']:10s} | {floor_str:5s} | {fees_str:10s} | {ownership_str:8s} | {direction_str:8s} | {status_str:10s} | {result['verdict']}")

    # Save results to JSON
    with open('verification_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\nResults saved to verification_results.json")

if __name__ == "__main__":
    main()
