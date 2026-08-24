#!/usr/bin/env python3
"""Quick test: scan Sumida + Koto only for new listings."""

import json
import re
import sys
import time
import urllib.request
import urllib.error

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)

KNOWN_NAMES = {
    "平井パーク・ホームズ", "ヴェラハイツ亀戸文花ユーフォニアス", "ルネ町屋",
    "ガーデンプラザ柴又弐番館", "ハイラーク大島", "四つ木パーク・ホームズ",
    "パークステージ小岩", "GSハイム第二金町", "ダイアパレス隅田公園",
}


def fetch_url(url, retries=2, backoff=1.5):
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
                print(f"[THROTTLE] Waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise Exception(f"Failed: {url}")


def parse_jsonld_list(html):
    """Extract JSON-LD ItemList from list page."""
    for match in re.finditer(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL
    ):
        content = match.group(1).strip()
        if "itemListElement" not in content:
            continue
        try:
            jsonld = json.loads(content)
        except json.JSONDecodeError:
            continue

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
                price_man = price_yen // 10000

                if name and url and price_yen > 0:
                    listings.append({"name": name, "url": url, "price_man": price_man})
            except (KeyError, ValueError, TypeError):
                continue
        return listings
    return []


def parse_detail_page(html):
    """Parse detail page."""
    result = {}
    for match in re.finditer(
        r'<th[^>]*>.*?<div class="fl">([^<]+)</div>.*?</th>\s*<td[^>]*>(.*?)</td>',
        html,
        re.DOTALL
    ):
        label = match.group(1).strip()
        value_html = match.group(2).strip()
        value = re.sub(r'<[^>]+>', '', value_html).strip()

        if "築年月" in label or "完成時期" in label:
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
        elif "所在階" in label or "階数" in label or "構造・階建" in label:
            result["floor"] = value
        elif "現況" in label:
            result["status"] = value
        elif "交通" in label or "駅" in label:
            result["access"] = value

    return result


def extract_year(year_str):
    if not year_str:
        return None
    m = re.search(r'(\d{4})年', year_str)
    return int(m.group(1)) if m else None


def extract_floor(floor_str):
    if not floor_str:
        return None, None
    m = re.search(r'(\d+)[階Ｆ](?:/.*?(\d+)[階Ｆ])?', floor_str)
    if m:
        return int(m.group(1)), int(m.group(2)) if m.group(2) else None
    return None, None


def extract_fees(mgmt_str, reserve_str):
    total = 0
    for fee_str in [mgmt_str, reserve_str]:
        if not fee_str or "なし" in fee_str or "－" in fee_str:
            continue
        m = re.search(r'(\d+)万?(\d*)円', fee_str)
        if m:
            val = int(m.group(1))
            if m.group(2):
                val = val * 10000 + int(m.group(2))
            elif "万" in fee_str:
                val = val * 10000
            total += val
    return total if total > 0 else None


def extract_size(size_str):
    if not size_str:
        return None
    m = re.search(r'(\d+\.?\d*)m', size_str)
    return float(m.group(1)) if m else None


# Scan Sumida and Koto only
print("=== QUICK TEST: Sumida + Koto ===")
for ward, jis_code in [("Sumida", 13107), ("Koto", 13108)]:
    print(f"\n{ward} (JIS={jis_code}):")

    # Fetch page 1
    url = f"https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{jis_code}/?page=1"
    try:
        html = fetch_url(url)
        listings = parse_jsonld_list(html)
        print(f"  Found {len(listings)} listings on page 1")

        # Detail-fetch first 3
        for item in listings[:3]:
            if item["price_man"] > 40000:
                continue
            if item["name"] in KNOWN_NAMES:
                continue

            print(f"    Fetching {item['name']}...")
            try:
                detail_html = fetch_url(item["url"])
                details = parse_detail_page(detail_html)

                year = extract_year(details.get("year"))
                floor, _ = extract_floor(details.get("floor"))
                size = extract_size(details.get("size"))
                fees = extract_fees(details.get("mgmt_fee"), details.get("reserve_fee"))

                print(f"      Year: {year}, Floor: {floor}, Size: {size}m2, Fees: {fees}")

                time.sleep(0.5)
            except Exception as e:
                print(f"      Error: {str(e)[:50]}")
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")

    time.sleep(1)

print("\n=== END ===")
