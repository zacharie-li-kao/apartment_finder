#!/usr/bin/env python3
"""Focused scan: Sumida + Koto priority wards for new 48h listings."""

import json
import re
import sys
import time
import urllib.request
import urllib.error

# Force UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)

# Known properties - minimal list for focusing on new ones
KNOWN_NAMES = {
    "平井パーク・ホームズ", "ヴェラハイツ亀戸文花ユーフォニアス", "ダイアパレス隅田公園",
    "グレースジュン", "住建第６ハイプレース",
}

def fetch_url(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ja",
            "Referer": "https://www.rehouse.co.jp/",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 503:
            time.sleep(3)
            return fetch_url(url)  # Retry once
        raise

def parse_jsonld_list(html):
    for match in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        content = match.group(1).strip()
        if "itemListElement" not in content:
            continue
        try:
            jsonld = json.loads(content)
        except:
            continue
        items = jsonld.get("itemListElement", [])
        if items:
            listings = []
            for item in items:
                try:
                    product = item.get("item", {})
                    name = product.get("name")
                    offers = product.get("offers", {})
                    url = offers.get("url")
                    price_yen = int(offers.get("price", 0))
                    if name and url and price_yen > 0:
                        listings.append({"name": name, "url": url, "price_man": price_yen//10000, "price_yen": price_yen})
                except:
                    pass
            return listings if listings else []
    return []

def parse_detail_page(html):
    result = {}
    # Vue-SSR pattern
    for match in re.finditer(
        r'<td class="table-header label"[^>]*><!--\[-->([^<]+)<!--\]--></td>\s*<td class="table-data content"[^>]*>.*?<!--\[-->([^<]+)<!--\]-->',
        html, re.DOTALL
    ):
        label = match.group(1).strip()
        value = match.group(2).strip()

        if "築年月" in label:
            result["year"] = value
        elif "土地権利" in label:
            result["ownership"] = value
        elif "管理費" in label and "管理費等" not in label:
            result["mgmt_fee"] = value
        elif "修繕積立金" in label:
            result["reserve_fee"] = value
        elif "向き" in label:
            result["direction"] = value
        elif "間取り" in label:
            result["layout"] = value
        elif "専有面積" in label:
            result["size"] = value
        elif "階数" in label:
            result["floor"] = value
        elif "現況" in label:
            result["status"] = value
        elif "交通" in label or "駅" in label:
            result["access"] = value

    if "direction" not in result:
        dir_match = re.search(r'(南東|南西|北東|北西|南|北|東|西)(?:向き|向)', html)
        if dir_match:
            result["direction"] = dir_match.group(1)

    return result

def extract_year(s):
    if not s:
        return None
    m = re.search(r'(\d{4})年', s)
    return int(m.group(1)) if m else None

def extract_floor(s):
    if not s:
        return None
    m = re.search(r'(\d+)[階Ｆ]', s)
    return int(m.group(1)) if m else None

def extract_size(s):
    if not s:
        return None
    m = re.search(r'(\d+\.?\d*)m', s)
    return float(m.group(1)) if m else None

def extract_fees(mgmt, reserve):
    total = 0
    for s in [mgmt, reserve]:
        if not s or "なし" in s or "－" in s or "無" in s:
            continue
        m = re.search(r'(\d+)万?(\d*)円', s)
        if m:
            val = int(m.group(1))
            if m.group(2):
                val = val * 10000 + int(m.group(2))
            elif "万" in s:
                val = val * 10000
            total += val
    return total if total > 0 else None

print("=" * 120)
print("REHOUSE 48H SCAN: Sumida + Koto Priority Wards")
print("=" * 120)

new_count = 0

for ward, jis_code in [("Sumida", 13107), ("Koto", 13108)]:
    print(f"\n{ward} (JIS={jis_code}):")

    page = 1
    while page <= 5:  # Max 5 pages
        url = f"https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{jis_code}/?page={page}"
        print(f"  Page {page}...", end=" ", flush=True)

        try:
            html = fetch_url(url)
            listings = parse_jsonld_list(html)

            if not listings:
                print("STOP (no listings)")
                break

            print(f"({len(listings)} items)")

            for item in listings:
                if item["price_man"] > 40000:
                    continue
                if item["name"] in KNOWN_NAMES:
                    continue

                # Detail-fetch
                try:
                    detail_html = fetch_url(item["url"])
                    details = parse_detail_page(detail_html)

                    year = extract_year(details.get("year"))
                    floor = extract_floor(details.get("floor"))
                    size = extract_size(details.get("size"))
                    fees = extract_fees(details.get("mgmt_fee"), details.get("reserve_fee"))

                    # Quick hard-criteria check
                    if year and year < 1982:
                        continue
                    if size and size < 30:
                        continue
                    if floor and floor < 2:
                        continue

                    print(f"    NEW: {item['name']:40} | {item['price_man']}万 | {size}m² | {details.get('layout', '?')} | {floor}F | {year} | {fees}¥/mo | {details.get('direction', '?')}")
                    new_count += 1

                    time.sleep(0.5)
                except Exception as e:
                    print(f"      (Detail error: {str(e)[:30]})")

        except Exception as e:
            print(f"ERROR: {str(e)[:50]}")
            break

        page += 1
        time.sleep(1)

print(f"\n{'='*120}")
print(f"TOTAL NEW LISTINGS FOUND: {new_count}")
print(f"(Filtered against {len(KNOWN_NAMES)} known properties)")
