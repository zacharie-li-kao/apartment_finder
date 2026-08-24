#!/usr/bin/env python3
"""Quick diagnostic of 4 corrected wards - show top 10 from each ward"""

import requests
import json
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

WARDS = [
    ('Sumida', 13107),
    ('Katsushika', 13122),
    ('Itabashi', 13119),
    ('Koto', 13108),
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
BASE_URL = "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{code}/"

def fetch_and_analyze(ward_name, code, max_listings=10):
    """Fetch first page and show analysis of top listings"""
    print(f"\n{'='*100}")
    print(f"{ward_name.upper()} (code {code})")
    print(f"{'='*100}\n")

    url = BASE_URL.format(code=code)
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.encoding = 'utf-8'

        # Extract ld+json
        match = re.search(
            r'<script type="application/ld\+json" data-hid="productList">(\{.+?"itemListElement".+?\})</script>',
            response.text,
            re.DOTALL
        )

        if not match:
            print("No listings found in ld+json")
            return

        data = json.loads(match.group(1))
        listings = data.get('itemListElement', [])[:max_listings]

        print(f"Top {len(listings)} listings (by price):\n")

        for idx, item_wrapper in enumerate(listings, 1):
            item = item_wrapper.get('item', {})
            building = item.get('name', 'N/A')
            price_yen = item.get('offers', {}).get('price', 'N/A')
            detail_url = item.get('offers', {}).get('url', '')

            # Convert price
            try:
                price_man = int(price_yen) / 10000 if price_yen != 'N/A' else 'N/A'
            except:
                price_man = 'N/A'

            print(f"{idx}. {building[:50]}")
            print(f"   Price: ¥{price_man}万" if price_man != 'N/A' else f"   Price: {price_yen}yen")
            print(f"   URL: {detail_url[:70]}")

            # Try to fetch detail page
            if detail_url:
                try:
                    detail_resp = requests.get(detail_url, headers=HEADERS, timeout=15)
                    detail_resp.encoding = 'utf-8'
                    text = detail_resp.text

                    # Extract key info
                    size_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎡|m²)', text)
                    room_m = re.search(r'(\d+S?LDK)', text)
                    year_m = re.search(r'(19[7-9]\d|20[0-2]\d)\s*年', text)
                    floor_m = re.search(r'(\d+)\s*階', text)
                    fees_m = re.search(r'(?:合計|月額|管理費)\s*[¥]?\s*(\d{1,5}(?:,\d{3})*)', text)

                    size_val = size_m.group(1) if size_m else 'N/A'
                    room_val = room_m.group(1) if room_m else 'N/A'
                    year_val = year_m.group(1) if year_m else 'N/A'
                    floor_val = floor_m.group(1) if floor_m else 'N/A'
                    fees_val = fees_m.group(1).replace(',', '') if fees_m else 'N/A'

                    print(f"   Size: {size_val}m² | Room: {room_val} | Year: {year_val} | Floor: {floor_val}F | Fees: ¥{fees_val}/mo")

                    # Quick filter check
                    checks = []
                    try:
                        if int(year_val) >= 1982:
                            checks.append("✓1982+")
                        else:
                            checks.append(f"✗pre82({year_val})")
                    except:
                        checks.append("✗year?")

                    try:
                        if float(size_val) >= 30:
                            checks.append("✓≥30m²")
                        else:
                            checks.append(f"✗<30({size_val})")
                    except:
                        checks.append("✗size?")

                    try:
                        if 'LDK' in str(room_val):
                            checks.append("✓LDK+")
                        else:
                            checks.append(f"✗<1LDK")
                    except:
                        checks.append("✗room?")

                    try:
                        if int(floor_val) >= 2:
                            checks.append("✓≥2F")
                        else:
                            checks.append(f"✗<2F")
                    except:
                        checks.append("✗floor?")

                    try:
                        if int(fees_val) <= 30000:
                            checks.append("✓≤30k")
                        else:
                            checks.append(f"✗>{fees_val}")
                    except:
                        checks.append("✗fees?")

                    try:
                        if int(price_man) <= 40:
                            checks.append("✓≤40M")
                        else:
                            checks.append(f"✗>{price_man}M")
                    except:
                        checks.append("✗price?")

                    print(f"   Filters: {' '.join(checks)}")

                except Exception as e:
                    print(f"   [Detail fetch error: {str(e)[:50]}]")

            print()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    print("CORRECTED WARDS DIAGNOSTIC - Top 10 from each ward")
    for ward_name, code in WARDS:
        fetch_and_analyze(ward_name, code, max_listings=10)
