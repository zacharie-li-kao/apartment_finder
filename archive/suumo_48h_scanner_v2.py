#!/usr/bin/env python3
"""
SUUMO 48-hour new listings scanner - Version 2 (improved error handling).
"""

import re
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from urllib.parse import urljoin
import sys

KNOWN_LISTINGS_FILE = "KNOWN_LISTINGS.json"

# All 23 Tokyo wards (excluding Adachi-ku)
WARDS = {
    "sumida": "Sumida-ku",
    "koto": "Koto-ku",
    "itabashi": "Itabashi-ku",
    "katsushika": "Katsushika-ku",
    "chuo": "Chuo-ku",
    "minato": "Minato-ku",
    "shibuya": "Shibuya-ku",
    "chiyoda": "Chiyoda-ku",
    "shinjuku": "Shinjuku-ku",
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
    "meguro": "Meguro-ku",
    "shinagawa": "Shinagawa-ku",
    "suginami": "Suginami-ku",
}

# Hard filter criteria
PRICE_MAX = 40_000_000
SIZE_MIN = 30.0
YEAR_MIN = 1982
WALK_MAX = 15
FLOOR_MIN = 2
FEES_MAX = 30_000

known_listings: Set[str] = set()
session_stats = {"pages_fetched": 0, "errors": 0, "rate_limited": 0}

def load_known_listings() -> Set[str]:
    """Load the set of known properties."""
    global known_listings

    if Path(KNOWN_LISTINGS_FILE).exists():
        try:
            with open(KNOWN_LISTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    known_listings = set(item.get("name", "") for item in data if item.get("name"))
                elif isinstance(data, dict):
                    known_listings = set(data.keys())
            print(f"[+] Loaded {len(known_listings)} known listings\n")
            return known_listings
        except Exception as e:
            print(f"[!] Could not load known listings: {e}\n")

    fallback_names = {
        "セザール久が原", "メゾン蓮根", "サンタウン立花１号棟", "エスカイア等々力",
        "タウンハイツ亀有２号棟", "晴紀館", "関町南パーク・ホームズ", "ライオンズ桜台",
        "グリーンパーク立石", "ダイアパレス立石", "コスモ堀切菖蒲園駅前",
        "ニューライフマンション木場", "エクレール亀戸",
    }
    known_listings = fallback_names
    print(f"[!] Using {len(known_listings)} fallback hardcoded listings\n")
    return known_listings

def fetch_url(url: str, delay: float = 1.0) -> Tuple[str, bool]:
    """
    Fetch URL via curl. Returns (html_content, was_rate_limited).
    Implements backoff and retry logic.
    """
    time.sleep(delay)

    headers = [
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Accept-Language: ja",
        "-H", "Referer: https://suumo.jp/",
    ]

    for attempt in range(2):
        try:
            # Use curl with --write-out to capture HTTP code
            cmd = ["curl", "-s", "-w", "%{http_code}", "-m", "15"] + headers + [url]
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore', timeout=20)

            if result.returncode != 0:
                session_stats["errors"] += 1
                if attempt == 0:
                    time.sleep(3)
                continue

            # Last 3 chars should be HTTP status
            output = result.stdout
            if len(output) < 3:
                continue

            status_code = output[-3:]
            html = output[:-3]

            try:
                status = int(status_code)
            except ValueError:
                # Fallback: assume 200 if no valid status
                status = 200
                html = output

            if status == 503:
                session_stats["rate_limited"] += 1
                print(f"      [503 rate limit]", end="", flush=True)
                if attempt == 0:
                    # Wait and retry
                    time.sleep(10)
                    continue
                return "", True

            if status == 200 and html:
                session_stats["pages_fetched"] += 1
                return html, False

            if attempt == 0:
                time.sleep(2)

        except Exception as e:
            session_stats["errors"] += 1
            if attempt == 0:
                time.sleep(2)

    return "", False

def extract_listings(html: str, ward_name: str) -> List[Dict]:
    """Extract listings from HTML."""
    listings = []

    if not html or len(html) < 100:
        return listings

    # Split by property_unit
    blocks = re.split(r'<div class="property_unit[^"]*"', html)

    for block in blocks[1:]:
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
                "floor_str": "",
                "year": 0,
                "year_str": "",
                "walk": 999,
                "walk_str": "",
                "station": "",
                "url": "",
            }

            # Name (required)
            name_match = re.search(r'<dt[^>]*>物件名</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if name_match:
                data["name"] = name_match.group(1).strip()
            else:
                continue

            # Price
            price_match = re.search(r'<span class="dottable-value">([0-9,]+万円)</span>', block)
            if price_match:
                price_str = price_match.group(1)
                price_num = int(price_str.replace(',', '').replace('万円', ''))
                data["price"] = price_num * 10_000
                data["price_str"] = price_str

            # Size
            size_match = re.search(r'>(\d+\.?\d*)m<sup>2</sup>', block)
            if size_match:
                data["size"] = float(size_match.group(1))
                data["size_str"] = f"{data['size']}m2"

            # Layout
            layout_match = re.search(r'<dt[^>]*>間取り</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if layout_match:
                data["layout"] = layout_match.group(1).strip()

            # Floor
            floor_match = re.search(r'<dt[^>]*>階数</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if floor_match:
                floor_str = floor_match.group(1)
                floor_match2 = re.search(r'(\d+)', floor_str)
                if floor_match2:
                    data["floor"] = int(floor_match2.group(1))
                    data["floor_str"] = floor_str.strip()

            # Year
            year_match = re.search(r'<dt[^>]*>築年月</dt>\s*<dd[^>]*>([^<]+)</dd>', block)
            if year_match:
                year_str = year_match.group(1).strip()
                year_match2 = re.search(r'(19|20)(\d{2})', year_str)
                if year_match2:
                    data["year"] = int(year_match2.group(1) + year_match2.group(2))
                    data["year_str"] = year_str

            # Walk time
            walk_match = re.search(r'徒歩(\d+)分', block)
            if walk_match:
                data["walk"] = int(walk_match.group(1))
                data["walk_str"] = f"{data['walk']}min"

            # Station
            station_match = re.search(r'「([^」]+)」\s*徒歩', block)
            if station_match:
                data["station"] = station_match.group(1).strip()

            # URL
            url_match = re.search(r'<a[^>]*href="([^"]*chuko[^"]*)"', block)
            if url_match:
                url = url_match.group(1)
                if url.startswith('/'):
                    url = "https://suumo.jp" + url
                data["url"] = url

            if data.get("name"):
                listings.append(data)

        except Exception as e:
            pass

    return listings

def passes_filters(listing: Dict) -> bool:
    """Check hard filters."""
    if listing["price"] <= 0 or listing["price"] > PRICE_MAX:
        return False
    if listing["size"] < SIZE_MIN:
        return False
    if listing["year"] < YEAR_MIN:
        return False
    if listing["walk"] > WALK_MAX:
        return False
    if listing["floor"] < FLOOR_MIN:
        return False
    return True

def scan_ward_pages(ward_code: str, ward_name: str, max_pages: int = 5) -> List[Dict]:
    """Scan a ward for all pages."""
    print(f"  {ward_name}...", flush=True)

    new_listings = []
    page = 1

    while page <= max_pages:
        base_url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward_code}/"
        if page == 1:
            url = f"{base_url}?et=15&kt=4000&mb=30&pc=100"
        else:
            url = f"{base_url}?et=15&kt=4000&mb=30&pc=100&page={page}"

        print(f"    p{page}...", end="", flush=True)

        html, rate_limited = fetch_url(url, delay=1.0 if page == 1 else 2.0)

        if rate_limited:
            print(" [rate limit, skipping ward]")
            break

        if not html:
            print(" [error]")
            break

        listings = extract_listings(html, ward_name)
        print(f" {len(listings)} found", flush=True)

        if not listings:
            break

        # Process listings
        for listing in listings:
            if listing["name"] in known_listings:
                continue

            if passes_filters(listing):
                new_listings.append(listing)
                print(f"      [NEW] {listing['name']:<30} {listing['price_str']:>10} {listing['size_str']:>8}", flush=True)

        if len(listings) < 50:
            break  # Last page

        page += 1
        time.sleep(2)

    if new_listings:
        print(f"  => {len(new_listings)} new qualified listings")
    else:
        print(f"  => No new qualified listings")

    return new_listings

def main():
    print("=" * 90)
    print("SUUMO 48-Hour New Listings Scanner v2")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Scanning all 23 Tokyo wards...")
    print("=" * 90 + "\n")

    load_known_listings()

    all_new = []

    # Priority order
    ward_list = [
        ("sumida", "Sumida-ku"),
        ("koto", "Koto-ku"),
        ("itabashi", "Itabashi-ku"),
        ("katsushika", "Katsushika-ku"),
        ("chuo", "Chuo-ku"),
        ("minato", "Minato-ku"),
        ("shibuya", "Shibuya-ku"),
        ("chiyoda", "Chiyoda-ku"),
        ("shinjuku", "Shinjuku-ku"),
        ("nerima", "Nerima-ku"),
        ("setagaya", "Setagaya-ku"),
        ("nakano", "Nakano-ku"),
        ("toshima", "Toshima-ku"),
        ("bunkyo", "Bunkyo-ku"),
        ("taito", "Taito-ku"),
        ("ota", "Ota-ku"),
        ("edogawa", "Edogawa-ku"),
        ("arakawa", "Arakawa-ku"),
        ("kita", "Kita-ku"),
        ("meguro", "Meguro-ku"),
        ("shinagawa", "Shinagawa-ku"),
        ("suginami", "Suginami-ku"),
    ]

    for ward_code, ward_name in ward_list:
        try:
            new = scan_ward_pages(ward_code, ward_name, max_pages=3)
            all_new.extend(new)
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "=" * 90)
    print(f"Total new qualified listings: {len(all_new)}")
    print(f"Pages fetched: {session_stats['pages_fetched']}")
    print(f"Rate limits: {session_stats['rate_limited']}, Errors: {session_stats['errors']}")
    print("=" * 90)

    # Output results
    if all_new:
        output_file = Path("SUUMO_48H_NEW_LISTINGS.tsv")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("WARD\tNAME\tPRICE\tSIZE\tLAYOUT\tFLOOR\tYEAR\tWALK\tSTATION\tURL\n")
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
                    listing["url"],
                ]
                f.write("\t".join(row) + "\n")

        print(f"\n[OK] TSV saved to {output_file}")

        json_file = Path("SUUMO_48H_NEW_LISTINGS.json")
        with open(json_file, "w", encoding="utf-8") as f:
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
                    "url": listing["url"],
                })
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"[OK] JSON saved to {json_file}\n")
        return json_data
    else:
        print("\nNo new qualified listings found.")
        return []

if __name__ == "__main__":
    results = main()
