#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify 18 specific SUUMO listings by fetching ward pages and extracting information.
"""

import requests
import re
import json
import time
import sys
import io
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# List of 18 buildings to verify with estimated wards
LISTINGS = [
    {"name": "モアステージ隅田", "price": "2380万円", "wards": ["sumida"]},
    {"name": "ビィ・フォルマ亀戸", "price": "3980万円", "wards": ["koto"], "dup_with": 3},
    {"name": "ビィ・フォルマ亀戸", "price": "3980万円", "wards": ["koto"], "dup_with": 2},
    {"name": "ＮＩＣアーバンハイム亀戸", "price": "3990万円", "wards": ["koto"]},
    {"name": "サンシャインハイツ", "price": "3290万円", "wards": ["koto"]},
    {"name": "大島ロイヤルマンション", "price": "3380万円", "wards": ["koto"]},
    {"name": "ツインシティ壱番館エトランズ東砂", "price": "3490万円", "wards": ["koto"]},
    {"name": "ツインシティ東砂アネックス", "price": "3980万円", "wards": ["koto"]},
    {"name": "グリーンパーク第2南綾瀬602号室", "price": "2699万円", "wards": ["edogawa", "arakawa"]},
    {"name": "ライオンズマンション柴又", "price": "2980万円", "wards": ["katsushika"]},
    {"name": "ネオコーポ金町", "price": "2980万円", "wards": ["katsushika"]},
    {"name": "NICアーバンハイム四つ木第２", "price": "3100万円", "wards": ["katsushika"]},
    {"name": "ライオンズマンション綾瀬", "price": "3580万円", "wards": ["arakawa", "adachi"]},
    {"name": "GSハイム第二金町", "price": "3790万円", "wards": ["katsushika"]},
    {"name": "コスモ西亀有", "price": "3790万円", "wards": ["katsushika"]},
    {"name": "新小岩パーク・ホームズ", "price": "3890万円", "wards": ["katsushika"]},
    {"name": "ニックハイム渋江公園", "price": "3980万円", "wards": ["arakawa"]},
    {"name": "ディナ・スカーラお花茶屋", "price": "3980万円", "wards": ["katsushika"]},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

WARD_CODES = {
    "sumida": "13107",  # 墨田区
    "koto": "13108",     # 江東区
    "edogawa": "13121",  # 江戸川区
    "katsushika": "13122",  # 葛飾区
    "arakawa": "13119",  # 荒川区
    "adachi": "13120",   # 足立区
}

def fetch_ward_listings(ward_name, page=1):
    """Fetch listings for a specific ward."""
    try:
        url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward_name}/"

        params = {
            "pj": page - 1,  # SUUMO uses 0-based page indexing
        }

        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()

        print(f"  Fetched {ward_name} page {page}")
        return response.content

    except requests.exceptions.Timeout:
        print(f"  Timeout fetching {ward_name}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {ward_name}: {e}")
        return None

def extract_listings_from_html(html_content, target_name):
    """Extract listing information from HTML for a specific building name."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Look for building name in the page
        text_content = soup.get_text()

        if target_name not in text_content:
            return None

        results = []

        # Look for building name in <dd> tags (SUUMO uses <dd class="dottable-vm"> for building names)
        for dd in soup.find_all('dd'):
            if target_name in dd.get_text():
                # Find the nearest link with nc_ code
                # Search in parent divs and nearby elements
                parent = dd.parent
                while parent:
                    # Look for links with nc_ in parent
                    for a_tag in parent.find_all('a', href=True):
                        href = a_tag.get('href', '')
                        if 'nc_' in href:
                            nc_match = re.search(r'nc_(\d+)', href)
                            if nc_match:
                                nc_code = nc_match.group(1)
                                results.append({
                                    "name": target_name,
                                    "nc_code": nc_code,
                                    "href": href,
                                    "source": "dd"
                                })
                                break
                    if results:
                        break
                    parent = parent.parent

        # Also search for links that contain nc_ and have the building name nearby
        if not results:
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '')
                if 'nc_' in href:
                    # Check if this link is near the target name
                    parent = a_tag.parent
                    parent_text = parent.get_text() if parent else ""
                    if target_name in parent_text:
                        nc_match = re.search(r'nc_(\d+)', href)
                        if nc_match:
                            nc_code = nc_match.group(1)
                            results.append({
                                "name": target_name,
                                "nc_code": nc_code,
                                "href": href,
                                "source": "link"
                            })

        return results if results else None

    except Exception as e:
        print(f"  Error extracting listings: {e}")
        return None

def fetch_detail_page_by_nc(nc_code, ward_name):
    """Fetch detail page using clean URL."""
    try:
        # Try the clean URL format first
        url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward_name}/nc_{nc_code}/"

        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 404:
            print(f"    Detail page not found at expected URL")
            return None

        response.raise_for_status()
        print(f"    Fetched detail page for nc_{nc_code}")

        return response.content

    except requests.exceptions.Timeout:
        print(f"    Timeout fetching detail page")
        return None
    except requests.exceptions.RequestException as e:
        print(f"    Error fetching detail page: {e}")
        return None

def extract_detail_info(html_content):
    """Extract detailed information from property detail page."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()

        info = {
            "floor": None,
            "fees": None,
            "ownership": None,
            "direction": None,
            "status": None,
        }

        # Extract floor (所在階)
        # Pattern: "所在階" followed by something like "2階" or find pattern in table cells
        floor_patterns = [
            r'所在階[^0-9]*(\d+)階',  # "所在階" followed by number and 階
            r'所在階[\/\s]+(\d+)階',   # "所在階 / 2階"
            r'(\d+)階?/[A-Z]*(\d+)階建',  # "2階/SRC6階建"
        ]
        for pattern in floor_patterns:
            match = re.search(pattern, text)
            if match:
                info["floor"] = int(match.group(1))
                break

        # Extract monthly fees (管理費 + 修繕積立金)
        # These are listed separately, need to add them
        kanrihi = 0
        shuzen = 0

        kanrihi_match = re.search(r'管理費[^0-9]*([0-9]+(?:,?[0-9]*)?)\s*(?:万?\s*)?円', text)
        if kanrihi_match:
            kanrihi_str = kanrihi_match.group(1).replace(',', '').replace('万', '')
            kanrihi = int(kanrihi_str) if kanrihi_str.isdigit() else 0

        shuzen_match = re.search(r'修繕積立金[^0-9]*([0-9]+(?:,?[0-9]*)?)\s*(?:万?\s*)?円', text)
        if shuzen_match:
            shuzen_str = shuzen_match.group(1).replace(',', '').replace('万', '')
            shuzen = int(shuzen_str) if shuzen_str.isdigit() else 0

        if kanrihi > 0 or shuzen > 0:
            info["fees"] = kanrihi + shuzen

        # Extract ownership (所有権 = freehold, 借地権 = leasehold)
        # Look for the specific pattern in the HTML
        if '所有権' in text:
            info["ownership"] = "所有権"
        if '借地権' in text:
            info["ownership"] = "借地権"

        # Extract direction/orientation (向き)
        # Pattern: "向き" followed by a direction
        direction_match = re.search(r'向き[^0-9]*([北東南西]+)', text)
        if direction_match:
            info["direction"] = direction_match.group(1)
        else:
            # Try another pattern
            directions = ['北', '北東', '東', '南東', '南', '南西', '西', '北西']
            for direction in directions:
                if direction + '向き' in text:
                    info["direction"] = direction
                    break

        # Extract occupancy status
        # Look for specific patterns
        if '空家' in text or '空き家' in text:
            info["status"] = "空家"
        elif '居住中' in text or 'オーナーチェンジ' in text:
            info["status"] = "居住中"
        # Also check for availability patterns
        elif '入居可能' in text or '即入可' in text:
            info["status"] = "空家"

        return info

    except Exception as e:
        print(f"    Error extracting detail info: {e}")
        return None

def verify_listing(listing_idx, listing):
    """Verify a single listing."""
    name = listing["name"]
    price = listing["price"]

    print(f"\n[{listing_idx}] Verifying: {name} ({price})")

    # Check if this is a duplicate
    if "dup_with" in listing:
        print(f"    → Duplicate of listing #{listing['dup_with']}, will fetch once")

    # Try each ward
    for ward in listing.get("wards", []):
        print(f"  Searching in {ward}...")

        # Fetch ward listings
        html_content = fetch_ward_listings(ward)
        if not html_content:
            continue

        # Extract listings for this building
        results = extract_listings_from_html(html_content, name)
        if not results:
            print(f"    Not found in {ward}")
            continue

        print(f"    Found {len(results)} result(s)")

        # Fetch detail page for the first result
        result = results[0]
        nc_code = result["nc_code"]
        print(f"    Using nc_{nc_code}")

        detail_html = fetch_detail_page_by_nc(nc_code, ward)
        if not detail_html:
            print(f"    Failed to fetch detail page")
            continue

        # Extract information
        info = extract_detail_info(detail_html)
        if info:
            return info

        time.sleep(1)  # Rate limiting between requests

    print(f"    ✗ Could not find or fetch {name}")
    return None

def main():
    """Main function to verify all listings."""
    print(f"Verifying {len(LISTINGS)} listings...\n")

    results = []
    for i, listing in enumerate(LISTINGS, 1):
        # Handle duplicates
        if "dup_with" in listing and listing["dup_with"] < i:
            print(f"\n[{i}] {listing['name']} ({listing['price']}) - DUPLICATE of #{listing['dup_with']}")
            # Copy result from duplicate
            dup_idx = listing["dup_with"] - 1
            if dup_idx < len(results):
                results.append(results[dup_idx].copy())
                results[-1]["index"] = i
            continue

        info = verify_listing(i, listing)

        # Determine verdict
        if info:
            floor_ok = info.get("floor") is not None and info["floor"] >= 2
            fees_ok = info.get("fees") is None or info["fees"] <= 30000
            ownership_ok = info.get("ownership") == "所有権"

            verdict = "✓ PASS" if (floor_ok and fees_ok and ownership_ok) else "✗ FAIL"

            reasons = []
            if not floor_ok:
                reasons.append(f"Floor issue (1F or missing)" if info.get("floor") is None else f"Floor 1F")
            if not fees_ok:
                reasons.append(f"Fees ¥{info['fees']:,} > 30,000")
            if not ownership_ok:
                reasons.append(f"Ownership: {info.get('ownership')}")

            result = {
                "index": i,
                "name": listing["name"],
                "price": listing["price"],
                "floor": info.get("floor"),
                "fees": info.get("fees"),
                "ownership": info.get("ownership"),
                "direction": info.get("direction"),
                "status": info.get("status"),
                "verdict": verdict,
                "reasons": reasons if verdict == "✗ FAIL" else []
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
                "status": None,
                "verdict": "❌ DATA NOT FOUND",
                "reasons": ["Unable to fetch or find listing"]
            }

        results.append(result)
        time.sleep(2)  # Rate limiting

    # Print results as table
    print("\n\n" + "="*120)
    print("VERIFICATION RESULTS")
    print("="*120)
    print(f"{'#':3} | {'Name':40} | {'Price':10} | {'Floor':6} | {'Fees/mo':10} | {'Ownership':8} | {'Direction':8} | {'Status':8} | Verdict")
    print("-" * 120)

    for result in results:
        floor_str = f"{result['floor']}F" if result["floor"] else "N/A"
        fees_str = f"¥{result['fees']:,}" if result["fees"] else "N/A"
        ownership_str = result["ownership"] or "N/A"
        direction_str = result["direction"] or "N/A"
        status_str = result["status"] or "N/A"

        print(f"{result['index']:3d} | {result['name']:40} | {result['price']:10} | {floor_str:6} | {fees_str:10} | {ownership_str:8} | {direction_str:8} | {status_str:8} | {result['verdict']}")

    # Print failure reasons
    print("\n" + "="*120)
    print("FAILURE DETAILS:")
    print("="*120)
    for result in results:
        if result["verdict"] in ["✗ FAIL", "❌ DATA NOT FOUND"] and result.get("reasons"):
            print(f"#{result['index']:2d} {result['name']:40} - {', '.join(result['reasons'])}")

    # Save results to JSON
    with open('verification_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to verification_results.json")

    # Print CSV format for easy copying
    print("\n" + "="*120)
    print("CSV FORMAT (for spreadsheet):")
    print("="*120)
    print("Name | Price | Floor | Fees/mo | Ownership | Direction | Status | Verdict")
    for result in results:
        floor_str = f"{result['floor']}F" if result["floor"] else "N/A"
        fees_str = f"¥{result['fees']:,}" if result["fees"] else "N/A"
        ownership_str = result["ownership"] or "N/A"
        direction_str = result["direction"] or "N/A"
        status_str = result["status"] or "N/A"

        print(f"{result['name']} | {result['price']} | {floor_str} | {fees_str} | {ownership_str} | {direction_str} | {status_str} | {result['verdict']}")

if __name__ == "__main__":
    main()
