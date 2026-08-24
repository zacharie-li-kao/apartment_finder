#!/usr/bin/env python3
"""
rehouse.co.jp 48h scan for new qualified listings across all 23 Tokyo wards.
Fetches list pages, detail-fetches, applies hard criteria, outputs TSV.
"""

import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from collections import defaultdict

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)

# All 23 Tokyo wards with JIS codes
WARDS = {
    "Chiyoda": 13101, "Chuo": 13102, "Minato": 13103, "Shinjuku": 13104,
    "Shibuya": 13105, "Taito": 13106, "Sumida": 13107, "Koto": 13108,
    "Bunkyo": 13109, "Toshima": 13110, "Ota": 13111, "Setagaya": 13112,
    "Meguro": 13113, "Nakano": 13114, "Suginami": 13115, "Kita": 13116,
    "Arakawa": 13118, "Itabashi": 13119, "Nerima": 13120, "Katsushika": 13121,
    "Edogawa": 13123,  # Adachi 13117 explicitly excluded per CLAUDE.md
}

# Known database (116 properties) — names to dedup against
KNOWN_NAMES = {
    "平井パーク・ホームズ", "ヴェラハイツ亀戸文花ユーフォニアス", "ルネ町屋",
    "ガーデンプラザ柴又弐番館", "ハイラーク大島", "名津葛西第二", "京成小岩グリーンプラザ",
    "クリオ志村ラ・モード", "東砂三丁目ハイツ6号棟", "オリンポス四つ木",
    "新小岩パーク・ホームズ", "ライオンズマンション東四つ木", "金町ハイツ",
    "日神パレステージ小岩第二", "さくらマンション小松川", "GSハイム第二金町",
    "四つ木パーク・ホームズ", "パークステージ小岩", "GSハイムときわ台",
    "キャッスルマンションお花茶屋", "ダイアパレス隅田公園", "グリーンキャピタル第三金町",
    "メイツときわ台", "キャニオンマンション常盤台", "レーベンハイム東武練馬",
    "メゾン蓮根", "キャニオンマンション西台", "エンゼルハイム王子",
    "ビラ大泉学園", "光シャンブル滝野川", "住建第６ハイプレース", "東高駒込ペアシティ",
    "カエサル西尾久", "バロンハイツ大島", "グレースジュン", "ベルシャトゥ新小岩",
    "ダイアパレス柴又",
    # Additional from June sweep
    "日神パレス新三河島", "ダイアパレス鷺宮", "東糀谷ダイヤモンドマンション",
    "セブンスターハイツ中野Ⅴ", "晴紀館", "ゼファー一之江", "清新北ハイツ7号棟",
    "三生エンゼルハイム中葛西", "メゾン・リバーサイド4号棟", "コスモ葛西シティフォルム",
    "エクセル西葛西", "セザール大森本町", "セザール久が原",
    # Known from before
    "パークステージ小岩", "カエサル西尾久", "京成小岩グリーンプラザ",
    "さくらマンション小松川", "セザール南砂町",  # eliminated
}

KNOWN_COUNT = 116


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def fetch_url(url, retries=3, backoff=2.0):
    """Fetch URL with throttle retry logic."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "ja",
                    "Referer": "https://www.rehouse.co.jp/",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 503:
                wait = backoff ** attempt
                log(f"  ⚠️ 503 throttle on {url[:60]}…, waiting {wait}s")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            log(f"  ❌ Error fetching {url[:60]}…: {e}")
            raise
    raise Exception(f"Failed after {retries} retries: {url}")


def parse_jsonld_list(html):
    """Extract JSON-LD ItemList from list page."""
    # Find all JSON-LD script tags and look for the one with itemListElement
    for match in re.finditer(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL
    ):
        content = match.group(1).strip()

        # Quick check if this script has itemListElement
        if "itemListElement" not in content:
            continue

        try:
            jsonld = json.loads(content)
        except json.JSONDecodeError:
            continue

        # Check if this is the product list
        items = jsonld.get("itemListElement", [])
        if not items:
            continue

        listings = []
        for item in items:
            try:
                product = item.get("item", {})
                name = product.get("name")
                offers = product.get("offers", {})
                url = offers.get("url")
                price_yen = int(offers.get("price", 0))
                price_man = price_yen // 10000  # Convert to 万

                if name and url and price_yen > 0:
                    listings.append({
                        "name": name,
                        "url": url,
                        "price_man": price_man,
                        "price_yen": price_yen,
                    })
            except (KeyError, ValueError, TypeError):
                continue

        return listings  # Return the first valid itemListElement found

    return []  # No valid itemListElement found


def parse_nuxt_state(html):
    """Extract Nuxt state blob for detail page fields."""
    # Look for the Nuxt JSON state blob
    match = re.search(r'<script id="__NUXT_DATA__"[^>]*>(\[.*?\])</script>', html, re.DOTALL)
    if not match:
        return {}

    try:
        state_json = json.loads(match.group(1))
    except:
        return {}

    # The state is typically flat key-value pairs or nested structure
    # Look for specific labels and their corresponding values
    result = {}

    # Search in the JSON blob for our target fields as strings
    state_str = json.dumps(state_json)

    # Extract key fields
    fields_to_extract = [
        ("築年月", "year"),
        ("土地権利", "ownership"),
        ("管理費等", "mgmt_fee"),
        ("修繕積立金", "reserve_fee"),
        ("向き", "direction"),
        ("間取り", "layout"),
        ("専有面積", "size"),
        ("所在階", "floor"),
        ("価格", "price"),
        ("現況", "status"),
        ("交通", "access"),
    ]

    for jp_label, field_name in fields_to_extract:
        # Try to find the label followed by its value
        pattern = f'"{jp_label}"[^}}]*"([^"]*)"'
        m = re.search(pattern, state_str)
        if m:
            result[field_name] = m.group(1)

    return result


def parse_detail_page(html):
    """Parse detail page for all required fields using table structure."""
    result = {}

    # Pattern 1: Vue-SSR with comments: <td class="table-header label"><!--[-->LABEL<!--]--></td><td>VALUE</td>
    for match in re.finditer(
        r'<td class="table-header label"[^>]*><!--\[-->([^<]+)<!--\]--></td>\s*<td class="table-data content"[^>]*>.*?<!--\[-->([^<]+)<!--\]-->',
        html,
        re.DOTALL
    ):
        label = match.group(1).strip()
        value = match.group(2).strip()

        if "築年月" in label:
            result["year"] = value
        elif "土地権利" in label:
            result["ownership"] = value
        elif "管理費等" in label or "管理費" in label:
            result["mgmt_fee"] = value
        elif "修繕積立金" in label:
            result["reserve_fee"] = value
        elif "向き" in label:
            result["direction"] = value
        elif "間取り" in label:
            result["layout"] = value
        elif "専有面積" in label:
            result["size"] = value
        elif "階数" in label or "階数 / 階建" in label:
            result["floor"] = value
        elif "現況" in label:
            result["status"] = value
        elif "交通" in label:
            result["access"] = value

    # Fallback Pattern 2: <th>...<div class="fl">LABEL</div>...</th>...<td>VALUE</td>
    if not result:
        for match in re.finditer(
            r'<th[^>]*>.*?<div class="fl">([^<]+)</div>.*?</th>\s*<td[^>]*>(.*?)</td>',
            html,
            re.DOTALL
        ):
            label = match.group(1).strip()
            value_html = match.group(2).strip()
            value = re.sub(r'<[^>]+>', '', value_html).strip()

            if "築年月" in label:
                result["year"] = value
            elif "土地権利" in label:
                result["ownership"] = value
            elif "管理費" in label:
                result["mgmt_fee"] = value
            elif "修繕積立金" in label:
                result["reserve_fee"] = value
            elif "向き" in label:
                result["direction"] = value
            elif "間取り" in label:
                result["layout"] = value
            elif "専有面積" in label:
                result["size"] = value
            elif "所在階" in label or "階数" in label:
                result["floor"] = value
            elif "現況" in label:
                result["status"] = value

    # Extract direction from free text if needed
    if "direction" not in result:
        dir_match = re.search(r'(南東|南西|北東|北西|南|北|東|西)(?:向き|向)', html)
        if dir_match:
            result["direction"] = dir_match.group(1)

    return result


def extract_year(year_str):
    """Extract year as integer from various formats."""
    if not year_str:
        return None
    # Match "1982年5月", "1982年05月", "1982年", etc.
    m = re.search(r'(\d{4})年', year_str)
    if m:
        return int(m.group(1))
    return None


def extract_floor(floor_str):
    """Extract floor number (X/Y) from various formats."""
    if not floor_str:
        return None, None
    # Match "2階/RC5階建", "2F/5F", "2階", etc.
    m = re.search(r'(\d+)[階Ｆ](?:/.*?(\d+)[階Ｆ])?', floor_str)
    if m:
        unit_floor = int(m.group(1))
        total_floors = int(m.group(2)) if m.group(2) else None
        return unit_floor, total_floors
    return None, None


def extract_fees(mgmt_str, reserve_str):
    """Extract monthly fees from various formats and sum them."""
    total = 0
    for fee_str in [mgmt_str, reserve_str]:
        if not fee_str or "なし" in fee_str or "無" in fee_str or "－" in fee_str:
            continue
        # Match "8,000円", "8000円", "1万6300円", etc.
        m = re.search(r'(\d+)万?(\d*)円', fee_str)
        if m:
            val = int(m.group(1))
            if m.group(2):  # Has decimal part
                val = val * 10000 + int(m.group(2))
            elif "万" in fee_str:  # "1万"
                val = val * 10000
            total += val
    return total if total > 0 else None


def extract_size(size_str):
    """Extract size in m² from various formats."""
    if not size_str:
        return None
    m = re.search(r'(\d+\.?\d*)m²', size_str)
    if m:
        return float(m.group(1))
    return None


def extract_access(access_str):
    """Extract walking time (minutes) from access string."""
    if not access_str:
        return None, None
    # Match "駅名5分", "駅名 5分", etc.
    parts = access_str.split()
    station = None
    walk_min = None

    for part in parts:
        if not station and any(c in part for c in "駅線"):
            station = part
        m = re.search(r'(\d+)分', part)
        if m:
            walk_min = int(m.group(1))

    return station, walk_min


def check_hard_criteria(listing):
    """Check if listing passes all hard criteria. Return (passes, reason)."""

    # 1. Price ≤40M yen
    if listing.get("price_man", float("inf")) > 40000:
        return False, f"Price {listing['price_man']}万 > 40M"

    # 2. Size ≥30m²
    size = listing.get("size")
    if size is None or size < 30:
        return False, f"Size {size}m² < 30m²"

    # 3. Layout ≥1LDK
    layout = listing.get("layout", "")
    if not layout or not any(c in layout for c in "LDK"):
        return False, f"Layout {layout} doesn't contain LDK"
    # Must have at least 1LDK
    if "1K" in layout or "1R" in layout or "2K" in layout:
        return False, f"Layout {layout} < 1LDK"

    # 4. Year ≥1982
    year = listing.get("year")
    if year is None or year < 1982:
        return False, f"Year {year} < 1982"

    # 5. Walk to station ≤15 min
    walk_min = listing.get("walk_min")
    if walk_min is None or walk_min > 15:
        return False, f"Walk {walk_min} min > 15"

    # 6. Floor ≥2F
    floor = listing.get("floor")
    if floor is None or floor < 2:
        return False, f"Floor {floor} < 2"

    # 7. Monthly fees ≤30,000 yen
    fees = listing.get("fees")
    if fees is None or fees > 30000:
        return False, f"Fees {fees}¥ > 30,000"

    # 8. Freehold only (所有権)
    ownership = listing.get("ownership", "")
    if "所有権" not in ownership:
        return False, f"Ownership {ownership} != 所有権"

    # 9. NOT North-facing only
    direction = listing.get("direction", "")
    if direction == "北":  # North only
        return False, f"Direction is North-only"

    return True, "PASS"


def scan_ward(jis_code, ward_name):
    """Scan a single ward for new listings."""
    new_listings = []

    # Scan all pages
    page = 1
    max_pages = 50  # Safety limit

    while page <= max_pages:
        url = f"https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{jis_code}/?page={page}"
        log(f"  Fetching {ward_name} page {page}…")

        try:
            html = fetch_url(url)
        except Exception as e:
            log(f"    Error fetching page {page}: {e}")
            break

        # Parse list page
        listings = parse_jsonld_list(html)
        if not listings:
            log(f"    No listings on page {page}, stopping pagination")
            break

        log(f"    Found {len(listings)} listings on page {page}")

        # Process each listing
        for item in listings:
            # Early filter by price
            if item["price_man"] > 40000:
                continue

            # Skip known names
            if item["name"] in KNOWN_NAMES:
                continue

            # Detail-fetch
            detail_url = f"https://www.rehouse.co.jp{item['url']}"
            try:
                detail_html = fetch_url(detail_url)
                time.sleep(1)  # Throttle between detail fetches
            except Exception as e:
                log(f"    Error fetching detail {item['name']}: {e}")
                continue

            # Parse detail page
            details = parse_detail_page(detail_html)

            # Merge listing data
            listing = {
                "name": item["name"],
                "url": detail_url,
                "price_man": item["price_man"],
                "price_yen": item["price_yen"],
            }

            # Extract and normalize fields
            listing["year"] = extract_year(details.get("year"))
            listing["size"] = extract_size(details.get("size"))
            listing["layout"] = details.get("layout", "").replace("　", " ").replace("Ａ", "A")
            listing["direction"] = details.get("direction", "")
            listing["ownership"] = details.get("ownership", "")
            listing["floor"], listing["total_floors"] = extract_floor(details.get("floor"))
            listing["fees"] = extract_fees(details.get("mgmt_fee"), details.get("reserve_fee"))
            listing["station"], listing["walk_min"] = extract_access(details.get("access"))
            listing["status"] = details.get("status", "")

            # Check hard criteria
            passes, reason = check_hard_criteria(listing)
            listing["criteria_check"] = reason

            if passes:
                listing["ward"] = ward_name
                new_listings.append(listing)
                log(f"    ✓ PASS: {item['name']} ({listing['price_man']}万, {listing['size']}m², {listing['layout']}, {listing['floor']}/{listing['total_floors']}F, {listing['year']}, {listing['walk_min']}min, {listing['fees']}¥)")

        page += 1
        time.sleep(2)  # Throttle between pages

    return new_listings


def main():
    log(f"Starting rehouse.co.jp scan for new 48h listings (cutoff: {(datetime.now() - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M')})")
    log(f"Known database: {KNOWN_COUNT} properties")
    log(f"Scanning {len(WARDS)} wards…\n")

    all_new = []
    priority_wards = ["Sumida", "Koto"]  # Scan these first
    remaining_wards = sorted([w for w in WARDS.keys() if w not in priority_wards])
    ward_order = priority_wards + remaining_wards

    for ward_name in ward_order:
        jis_code = WARDS[ward_name]
        log(f"\nScanning {ward_name} (JIS={jis_code})…")

        try:
            new = scan_ward(jis_code, ward_name)
            all_new.extend(new)
            log(f"  → {len(new)} NEW qualifying listings found in {ward_name}")
        except Exception as e:
            log(f"  ❌ Error scanning {ward_name}: {e}")

    # Output TSV
    print("\n" + "=" * 150)
    print("NEW LISTINGS (TSV)")
    print("=" * 150)
    print("WARD\tNAME\tPRICE(万)\tSIZE(m²)\tLAYOUT\tFLOOR(X/Y)\tYEAR\tWALK(min)\tSTATION\tDIRECTION\tFEES(¥/mo)\tOWNERSHIP\tSTATUS\tURL")

    for item in sorted(all_new, key=lambda x: x.get("price_man", float("inf"))):
        print(
            f"{item['ward']}\t"
            f"{item['name']}\t"
            f"{item['price_man']}\t"
            f"{item['size']}\t"
            f"{item['layout']}\t"
            f"{item['floor']}/{item['total_floors']}\t"
            f"{item['year']}\t"
            f"{item['walk_min']}\t"
            f"{item['station'] or '?'}\t"
            f"{item['direction'] or '?'}\t"
            f"{item['fees'] or '?'}\t"
            f"{item['ownership'] or '?'}\t"
            f"{item['status'] or '?'}\t"
            f"{item['url']}"
        )

    print("\n" + "=" * 150)
    print(f"TOTAL NEW: {len(all_new)} qualifying listings (unique names)")
    print(f"TOTAL KNOWN: {KNOWN_COUNT}")
    print(f"RUNNING TOTAL: {KNOWN_COUNT + len(all_new)}")


if __name__ == "__main__":
    main()
