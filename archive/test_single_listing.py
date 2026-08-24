#!/usr/bin/env python3
"""Debug: test a single listing to understand parsing issues"""

import requests
import json
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Test a known listing from Koto that appeared in the original results
# ガーデンプラザ柴又弐番館 - should be 2,980万 according to findings.md
detail_url = "https://www.rehouse.co.jp/buy/mansion/bkdetail/FM5BGA45/"

print("Testing single listing fetch and parse")
print("="*80)
print(f"URL: {detail_url}\n")

# Fetch the page
response = requests.get(detail_url, headers=HEADERS, timeout=20)
response.encoding = 'utf-8'
html = response.text

print("Page fetched successfully")
print(f"Page length: {len(html)} chars\n")

# Try to extract detail info
text = html

# Price
price_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎡|m²)', text)
print(f"Size: {price_match.group(1) if price_match else 'NOT FOUND'}m²")

# Room type
room_match = re.search(r'(\d+S?LDK|Studio)', text)
print(f"Room: {room_match.group(1) if room_match else 'NOT FOUND'}")

# Year
year_match = re.search(r'(19[7-9]\d|20[0-2]\d)\s*年', text)
print(f"Year: {year_match.group(1) if year_match else 'NOT FOUND'}")

# Floor
floor_match = re.search(r'(\d+)\s*階|(\d+)\s*/\s*(\d+)', text)
if floor_match:
    if floor_match.group(3):
        print(f"Floor: {floor_match.group(2)}/{floor_match.group(3)}")
    else:
        print(f"Floor: {floor_match.group(1)}")
else:
    print("Floor: NOT FOUND")

# Direction
for direction in ['南東', '南西', '北東', '北西', '南', '北', '東', '西']:
    if direction + '向' in text or f'向{direction}' in text:
        print(f"Direction: {direction}向")
        break

# Ownership
if '所有権' in text:
    print("Ownership: 所有権 (Freehold)")
elif '借地権' in text:
    print("Ownership: 借地権 (Leasehold)")
else:
    print("Ownership: NOT FOUND")

# Fees - try multiple patterns
print("\nFee extraction debug:")
fee_patterns = [
    (r'(?:合計|管理費\+修繕|月額|管理費)\s*[¥]?\s*(\d{1,5}(?:,\d{3})*)\s*(?:円|万)?(?:/月|\/月)', "Pattern 1: 合計/月額"),
    (r'(\d{1,5}(?:,\d{3})*)\s*円\s*(?:/月|＋)', "Pattern 2: X円/月"),
    (r'¥(\d{1,6}(?:,\d{3})*)', "Pattern 3: ¥X"),
    (r'(\d{4,5})\s*(?:円|/月)', "Pattern 4: X円 or X/月"),
]

for pattern, desc in fee_patterns:
    match = re.search(pattern, text)
    if match:
        print(f"  {desc}: FOUND - '{match.group(1)}'")
    else:
        print(f"  {desc}: NOT FOUND")

# Also try to extract pricing info from ld+json if available
print("\nChecking for ld+json price data:")
match = re.search(r'<script type="application/ld\+json" data-hid="productList">(\{.+?"itemListElement".+?\})</script>', html, re.DOTALL)
if not match:
    print("  ProductList ld+json NOT FOUND")
else:
    try:
        data = json.loads(match.group(1))
        if 'itemListElement' in data and len(data['itemListElement']) > 0:
            item = data['itemListElement'][0]['item']
            price_yen = item.get('offers', {}).get('price', 'NOT FOUND')
            print(f"  Price from ld+json: {price_yen} yen")
            if price_yen != 'NOT FOUND':
                price_man = int(price_yen) / 10000
                print(f"  Converted to 万円: {price_man:.0f}万")
    except Exception as e:
        print(f"  Error parsing ld+json: {e}")

# Show a snippet of the HTML around '管理費'  or '月額'
print("\n\nSearching for fee-related text in page...")
for match in re.finditer(r'.{0,50}(?:管理費|月額|修繕).{0,100}', text):
    print(f"  Found: ...{match.group(0)}...")
    if len(re.findall(r'.*?.{0,50}(?:管理費|月額|修繕).{0,100}.*?', text)) > 5:
        break
