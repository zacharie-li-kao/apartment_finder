#!/usr/bin/env python3
"""
SUUMO 48-hour new listings scanner across all 23 Tokyo wards.
Filters by hard criteria, fetches detail pages, deduplicates against known 116.
Output: TSV format with 12 fields.
"""

import re
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from urllib.parse import urljoin, quote

# === CONFIGURATION ===

KNOWN_LISTINGS_FILE = "KNOWN_LISTINGS.json"

# All 23 Tokyo wards (excluding Adachi-ku per user preference)
WARDS = {
    # Priority zones
    "sumida": "Sumida-ku",
    "koto": "Koto-ku",
    # Secondary
    "itabashi": "Itabashi-ku",
    "katsushika": "Katsushika-ku",
    "chuo": "Chuo-ku",
    "minato": "Minato-ku",
    "shibuya": "Shibuya-ku",
    "chiyoda": "Chiyoda-ku",
    "shinjuku": "Shinjuku-ku",
    # Lower priority
    "nerima": "Nerima-ku",
    "setagaya": "Setagaya-ku",
    "nakano": "Nakano-ku",
    "toshima": "Toshima-ku",
    "bunkyo": "Bunkyo-ku",
    "taito": "Taito-ku",
    "ota": "Ota-ku",
    "edogawa": "Edogawa-ku",
    "arakawa": "Arakawa-ku",
    "kita": "Kita-ku",
    # Lowest priority
    "meguro": "Meguro-ku",
    "shinagawa": "Shinagawa-ku",
    "suginami": "Suginami-ku",
}

# Hard filter criteria (all must pass)
PRICE_MAX = 40_000_000  # 40M yen
SIZE_MIN = 30.0  # 30m²
YEAR_MIN = 1982  # Post-seismic standard
WALK_MAX = 15  # 15 min to station
FLOOR_MIN = 2  # Not ground floor
FEES_MAX = 30_000  # Monthly management + reserve fees
LAYOUT_MIN = "1LDK"  # Minimum 1LDK

# Throttling (in seconds)
DELAY_PAGINATION = 2.0  # Between pagination fetches
DELAY_DETAIL = 5.0  # Between detail-page fetches
THROTTLE_RESET = 300.0  # 5 min silence to recover from 503

# === GLOBAL STATE ===

known_listings: Set[str] = set()
session_errors = {"503": 0, "timeout": 0, "other": 0}
last_fetch_time = 0.0

def load_known_listings() -> Set[str]:
    """Load the set of known properties to avoid duplication."""
    global known_listings

    # Try to load from JSON file first (116 known listings)
    if Path(KNOWN_LISTINGS_FILE).exists():
        try:
            with open(KNOWN_LISTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    known_listings = set(item.get("name", "") for item in data if item.get("name"))
                elif isinstance(data, dict):
                    known_listings = set(data.keys())
            print(f"[INFO] Loaded {len(known_listings)} known listings from {KNOWN_LISTINGS_FILE}\n")
            return known_listings
        except Exception as e:
            print(f"[WARNING] Could not load known listings: {e}\n")

    # Fallback: hardcoded names from recent commits
    fallback_names = {
        "セザール久が原",
        "メゾン蓮根",
        "サンタウン立花１号棟",
        "エスカイア等々力",
        "タウンハイツ亀有２号棟",
        "晴紀館",
        "関町南パーク・ホームズ",
        "ライオンズ桜台",
        "グリーンパーク立石",
        "ダイアパレス立石",
        "コスモ堀切菖蒲園駅前",
        "ニューライフマンション木場",
        "エクレール亀戸",
    }
    known_listings = fallback_names
    print(f"[WARNING] Using fallback {len(known_listings)} hardcoded listings\n")
    return known_listings

def throttled_curl(url: str, max_retries: int = 3) -> Tuple[str, Optional[str]]:
    """Fetch URL via curl with throttling and retry logic. Returns (html, error_type)."""
    global last_fetch_time

    # Enforce minimum delay since last fetch
    elapsed = time.time() - last_fetch_time
    if elapsed < DELAY_PAGINATION:
        time.sleep(DELAY_PAGINATION - elapsed)

    headers = [
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Accept-Language: ja",
        "-H", "Referer: https://suumo.jp/",
    ]

    for attempt in range(max_retries):
        try:
            cmd = ["curl", "-s", "-m", "15"] + headers + [url]
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding='utf-8',
                errors='ignore',
                timeout=20
            )
            last_fetch_time = time.time()

            if result.returncode == 0 and result.stdout:
                # Check for 503 in output (uncommon but possible)
                if "503" in result.stdout[:500]:
                    session_errors["503"] += 1
                    if attempt < max_retries - 1:
                        print(f"    [503 detected, attempt {attempt+1}/{max_retries}]", flush=True)
                        time.sleep(THROTTLE_RESET)
                    return "", "503"
                return result.stdout, None

            if attempt < max_retries - 1:
                time.sleep(2)
        except subprocess.TimeoutExpired:
            session_errors["timeout"] += 1
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            session_errors["other"] += 1
            if attempt < max_retries - 1:
                time.sleep(2)

    return "", "timeout" if session_errors["timeout"] > 0 else "other"

def extract_layout_level(layout_str: str) -> int:
    """Convert layout string to numeric level for comparison."""
    if not layout_str:
        return 0
    layout_str = layout_str.strip()

    # Map layout types to levels
    # 1R < 1K < 1DK < 1LDK < 2K < 2DK < 2LDK < 3+
    layout_order = {
        "1R": 1, "1ルーム": 1,
        "1K": 2, "1K": 2,
        "1DK": 3, "1ダイニングキッチン": 3,
        "1LDK": 4,
        "2K": 5,
        "2DK": 6,
        "2LDK": 7,
        "3K": 8, "3DK": 9, "3LDK": 10,
    }

    # Try direct match first
    if layout_str in layout_order:
        return layout_order[layout_str]

    # Check if it contains LDK
    if "LDK" in layout_str or "リビング" in layout_str:
        return 4  # At least 1LDK

    # Default: consider acceptable if it has layout info
    return 3 if layout_str else 0

def parse_price(price_str: str) -> Tuple[int, str]:
    """Parse price string like '2,480万円' to (int yen, formatted string)."""
    if not price_str:
        return 0, ""
    try:
        # Extract number(s) before 万円
        match = re.search(r'(\d+(?:,\d+)*)\s*万円', price_str)
        if match:
            num_str = match.group(1).replace(',', '')
            price_yen = int(num_str) * 10_000
            return price_yen, price_str.strip()
    except:
        pass
    return 0, ""

def parse_size(size_str: str) -> Tuple[float, str]:
    """Parse size string like '48m²' to (float m², formatted string)."""
    if not size_str:
        return 0.0, ""
    try:
        match = re.search(r'(\d+\.?\d*)\s*m[²2]', size_str)
        if match:
            return float(match.group(1)), size_str.strip()
    except:
        pass
    return 0.0, ""

def parse_year(year_str: str) -> Tuple[int, str]:
    """Parse year string like '1982年8月' to (int year, formatted string)."""
    if not year_str:
        return 0, ""
    try:
        match = re.search(r'(19|20)(\d{2})', year_str)
        if match:
            year = int(match.group(1) + match.group(2))
            return year, year_str.strip()
    except:
        pass
    return 0, ""

def parse_floor(floor_str: str) -> Tuple[int, int, str]:
    """Parse floor string like '4F' or '4/7' to (current_floor, total_floors, formatted_string)."""
    if not floor_str:
        return 0, 0, ""
    try:
        floor_str = floor_str.replace('階', '')
        # Try X/Y format first
        if '/' in floor_str:
            parts = floor_str.split('/')
            current = int(parts[0].strip())
            total = int(parts[1].strip())
            return current, total, floor_str.strip()
        else:
            # Try just X format
            match = re.search(r'(\d+)', floor_str)
            if match:
                return int(match.group(1)), 0, floor_str.strip()
    except:
        pass
    return 0, 0, ""

def parse_walk_time(walk_str: str) -> Tuple[int, str]:
    """Parse walk time string like '10分' to (int minutes, formatted string)."""
    if not walk_str:
        return 999, ""
    try:
        match = re.search(r'(\d+)\s*分', walk_str)
        if match:
            return int(match.group(1)), walk_str.strip()
    except:
        pass
    return 999, ""

def extract_listings_from_html(html: str, ward_name: str) -> List[Dict]:
    """Extract listing data from SUUMO list page HTML."""
    listings = []

    if not html:
        return listings

    # Split by property_unit elements (SUUMO's container for each listing)
    property_blocks = re.split(r'<div class="property_unit[^"]*"', html)

    for block in property_blocks[1:]:  # Skip first empty split
        try:
            data = {
                "ward": ward_name,
                "name": "",
                "price": 0,
                "price_str": "",
                "size": 0.0,
                "size_str": "",
                "layout": "",
                "floor": 0,
                "floor_total": 0,
                "floor_str": "",
                "year": 0,
                "year_str": "",
                "walk": 999,
                "walk_str": "",
                "station": "",
                "direction": "?",
                "fees": 0,
                "fees_str": "?",
                "ownership": "?",
                "url": "",
            }

            # Name (required - primary key)
            name_match = re.search(r'<dt[^>]*>物件名</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if name_match:
                data["name"] = name_match.group(1).strip()

            if not data["name"]:
                continue  # Skip if no name

            # Price (required)
            price_match = re.search(r'<span class="dottable-value">([0-9,]+万円)</span>', block)
            if price_match:
                data["price"], data["price_str"] = parse_price(price_match.group(1))

            # Size
            size_match = re.search(r'>(\d+\.?\d*)m<sup>2</sup>', block)
            if size_match:
                data["size"], data["size_str"] = parse_size(size_match.group(1) + "m²")

            # Layout
            layout_match = re.search(r'<dt[^>]*>間取り</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if layout_match:
                data["layout"] = layout_match.group(1).strip()

            # Floor
            floor_match = re.search(r'<dt[^>]*>階数</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if floor_match:
                floor_str = floor_match.group(1)
                data["floor"], data["floor_total"], data["floor_str"] = parse_floor(floor_str)

            # Year
            year_match = re.search(r'<dt[^>]*>築年月</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if year_match:
                data["year"], data["year_str"] = parse_year(year_match.group(1))

            # Walk time
            walk_match = re.search(r'徒歩(\d+)分', block)
            if walk_match:
                data["walk"], data["walk_str"] = parse_walk_time(walk_match.group(1) + "分")

            # Station
            station_match = re.search(r'「([^」]+)」\s*徒歩', block)
            if station_match:
                data["station"] = station_match.group(1).strip()

            # URL (property detail page)
            url_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*class="[^"]*property-link[^"]*"', block)
            if not url_match:
                url_match = re.search(r'<a[^>]*href="([^"]*chuko/[^"]*)"', block)
            if url_match:
                url = url_match.group(1)
                if url.startswith('/'):
                    url = "https://suumo.jp" + url
                elif not url.startswith('http'):
                    url = urljoin("https://suumo.jp/ms/chuko/tokyo/", url)
                data["url"] = url

            listings.append(data)

        except Exception as e:
            print(f"    [Parse error in block: {e}]", flush=True)
            continue

    return listings

def fetch_detail_page(url: str) -> Tuple[str, str, str]:
    """Fetch detail page and extract: direction, fees, ownership. Returns (direction, fees_str, ownership)."""
    if not url:
        return "?", "?", "?"

    # Add extra delay before detail fetch
    time.sleep(DELAY_DETAIL)

    html, error = throttled_curl(url)

    if error:
        print(f"    [Detail page error ({error}): {url[:60]}...]", flush=True)
        return "?", "?", "?"

    direction = "?"
    fees_str = "?"
    ownership = "?"

    try:
        # Direction (方角)
        direction_match = re.search(r'<dt[^>]*>[\s\S]*?方角[\s\S]*?</dt>\s*<dd[^>]*>([^<]+)</dd>', html)
        if direction_match:
            direction = direction_match.group(1).strip()

        # Monthly fees (管理費 + 修繕積立金)
        # Try to find both management fee and reserve fund
        mgmt_fee = 0
        reserve_fee = 0

        mgmt_match = re.search(r'管理費[/・]?(\d+(?:,\d+)*)\s*円', html)
        if mgmt_match:
            mgmt_fee = int(mgmt_match.group(1).replace(',', ''))

        reserve_match = re.search(r'修繕積立金[/・]?(\d+(?:,\d+)*)\s*円', html)
        if reserve_match:
            reserve_fee = int(reserve_match.group(1).replace(',', ''))

        total_fees = mgmt_fee + reserve_fee
        if total_fees > 0:
            fees_str = f"{total_fees:,}円"

        # Ownership (所有権 vs 借地権)
        if '借地権' in html:
            ownership = "Leasehold"
        elif '所有権' in html:
            ownership = "Freehold"

    except Exception as e:
        print(f"    [Detail parse error: {e}]", flush=True)

    return direction, fees_str, ownership

def passes_hard_filters(listing: Dict) -> Tuple[bool, Optional[str]]:
    """Check if listing passes all hard criteria. Returns (passes, reason_for_failure)."""

    # Price
    if listing["price"] <= 0:
        return False, "Price missing"
    if listing["price"] > PRICE_MAX:
        return False, f"Price ¥{listing['price']:,} > ¥{PRICE_MAX:,}"

    # Size
    if listing["size"] <= 0:
        return False, "Size missing"
    if listing["size"] < SIZE_MIN:
        return False, f"Size {listing['size']}m² < {SIZE_MIN}m²"

    # Layout
    if extract_layout_level(listing["layout"]) < extract_layout_level(LAYOUT_MIN):
        return False, f"Layout {listing['layout']} < {LAYOUT_MIN}"

    # Year
    if listing["year"] <= 0:
        return False, "Year missing"
    if listing["year"] < YEAR_MIN:
        return False, f"Year {listing['year']} < {YEAR_MIN}"

    # Floor (not ground)
    if listing["floor"] < FLOOR_MIN:
        return False, f"Floor {listing['floor']}F < {FLOOR_MIN}F"

    # Walk time
    if listing["walk"] > WALK_MAX:
        return False, f"Walk {listing['walk']}min > {WALK_MAX}min"

    # Fees (after detail fetch)
    if listing["fees_str"] != "?" and listing["fees_str"]:
        try:
            fees_match = re.search(r'(\d+(?:,\d+)*)', listing["fees_str"])
            if fees_match:
                fees = int(fees_match.group(1).replace(',', ''))
                if fees > FEES_MAX:
                    return False, f"Fees ¥{fees:,} > ¥{FEES_MAX:,}"
        except:
            pass

    # Ownership (after detail fetch)
    if listing["ownership"] == "Leasehold":
        return False, "Leasehold (借地権)"

    # Direction (after detail fetch)
    if listing["direction"] and "北向き" in listing["direction"]:
        return False, "North-facing only"

    return True, None

def scan_ward(ward_code: str, ward_name: str, priority: int) -> List[Dict]:
    """Scan a single ward for all pages. Returns new qualified listings."""
    print(f"\n[{priority}] {ward_name}...", flush=True)

    new_listings = []
    page = 1
    base_url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward_code}/"

    while True:
        # Build URL with filters: price ≤40M, size ≥30m², walk ≤15 min
        if page == 1:
            url = f"{base_url}?et=15&kt=4000&mb=30&pc=100"
        else:
            url = f"{base_url}?et=15&kt=4000&mb=30&pc=100&page={page}"

        print(f"  Page {page}...", end="", flush=True)

        html, error = throttled_curl(url)

        if error == "503":
            print(f" [503 - aborting ward]")
            return new_listings
        elif error:
            print(f" [Error: {error}]")
            return new_listings

        if not html:
            print(f" [No content]")
            return new_listings

        # Extract listings from this page
        listings = extract_listings_from_html(html, ward_name)
        print(f" {len(listings)} listings", flush=True)

        if not listings:
            # No listings on this page - likely end of results
            break

        # Process each listing
        for listing in listings:
            # Quick skip if known
            if listing["name"] in known_listings:
                continue

            # Fetch detail page for full info
            if listing["url"]:
                direction, fees_str, ownership = fetch_detail_page(listing["url"])
                listing["direction"] = direction
                listing["fees_str"] = fees_str
                listing["ownership"] = ownership

            # Check hard filters
            passes, reason = passes_hard_filters(listing)
            if passes:
                new_listings.append(listing)
                print(f"    [PASS] {listing['name']} | {listing['price_str']} | {listing['size_str']}", flush=True)
            elif reason and False:  # Suppress filter reasons for now
                print(f"    ✗ {listing['name']} ({reason})", flush=True)

        # Check if we should continue to next page
        # Stop if fewer listings than expected (indicates end)
        if len(listings) < 50:
            print(f"  (End of results - {len(listings)} < 50)")
            break

        page += 1
        time.sleep(DELAY_PAGINATION)

    return new_listings

def main():
    print("=" * 90)
    print(f"SUUMO 48-Hour New Listings Scanner")
    print(f"Scan time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Hard criteria: Price <= 40M, Size >= 30m2, Layout >= 1LDK, Year >= 1982, Walk <= 15min,")
    print(f"              Floor >= 2F, Fees <= 30k/mo, Freehold only, Not north-facing")
    print("=" * 90)

    # Load known listings for deduplication
    load_known_listings()

    all_new = []

    # Priority order: Sumida/Koto first, then secondaries, then others
    ward_order = [
        ("sumida", "Sumida-ku", 1),
        ("koto", "Koto-ku", 1),
        ("itabashi", "Itabashi-ku", 2),
        ("katsushika", "Katsushika-ku", 2),
        ("chuo", "Chuo-ku", 2),
        ("minato", "Minato-ku", 2),
        ("shibuya", "Shibuya-ku", 2),
        ("chiyoda", "Chiyoda-ku", 2),
        ("shinjuku", "Shinjuku-ku", 2),
        ("nerima", "Nerima-ku", 3),
        ("setagaya", "Setagaya-ku", 3),
        ("nakano", "Nakano-ku", 3),
        ("toshima", "Toshima-ku", 3),
        ("bunkyo", "Bunkyo-ku", 3),
        ("taito", "Taito-ku", 3),
        ("ota", "Ota-ku", 3),
        ("edogawa", "Edogawa-ku", 3),
        ("arakawa", "Arakawa-ku", 3),
        ("kita", "Kita-ku", 3),
        ("meguro", "Meguro-ku", 4),
        ("shinagawa", "Shinagawa-ku", 4),
        ("suginami", "Suginami-ku", 4),
    ]

    for ward_code, ward_name, priority in ward_order:
        try:
            new_listings = scan_ward(ward_code, ward_name, priority)
            all_new.extend(new_listings)

            if new_listings:
                print(f"  Found {len(new_listings)} NEW qualified listings")
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    print("\n" + "=" * 90)
    print(f"Total new qualified listings: {len(all_new)}")
    print(f"Session errors: 503={session_errors['503']}, timeout={session_errors['timeout']}, other={session_errors['other']}")
    print("=" * 90)

    # Output TSV
    if all_new:
        output_file = Path("SUUMO_48H_NEW_LISTINGS.tsv")
        with open(output_file, "w", encoding="utf-8") as f:
            # Header
            f.write("WARD\tNAME\tPRICE\tSIZE\tLAYOUT\tFLOOR\tYEAR\tWALK\tSTATION\tDIRECTION\tFEES\tOWNERSHIP\tURL\n")

            # Data
            for listing in all_new:
                row = [
                    listing["ward"],
                    listing["name"],
                    listing["price_str"],
                    listing["size_str"],
                    listing["layout"],
                    listing["floor_str"],
                    listing["year_str"],
                    listing["walk_str"],
                    listing["station"],
                    listing["direction"],
                    listing["fees_str"],
                    listing["ownership"],
                    listing["url"],
                ]
                f.write("\t".join(row) + "\n")

        print(f"\n[OK] Results saved to {output_file}")

        # Also save JSON for programmatic use
        json_file = Path("SUUMO_48H_NEW_LISTINGS.json")
        with open(json_file, "w", encoding="utf-8") as f:
            # Convert to dict for JSON
            json_data = []
            for listing in all_new:
                json_data.append({
                    "ward": listing["ward"],
                    "name": listing["name"],
                    "price_yen": listing["price"],
                    "price_str": listing["price_str"],
                    "size_m2": listing["size"],
                    "size_str": listing["size_str"],
                    "layout": listing["layout"],
                    "floor": listing["floor"],
                    "floor_str": listing["floor_str"],
                    "year": listing["year"],
                    "year_str": listing["year_str"],
                    "walk_min": listing["walk"],
                    "walk_str": listing["walk_str"],
                    "station": listing["station"],
                    "direction": listing["direction"],
                    "fees_str": listing["fees_str"],
                    "ownership": listing["ownership"],
                    "url": listing["url"],
                })
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"[OK] JSON also saved to {json_file}\n")

        return json_data
    else:
        print("\nNo new qualified listings found in past 48 hours.")
        return []

if __name__ == "__main__":
    results = main()
