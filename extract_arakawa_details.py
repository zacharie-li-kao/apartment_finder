#!/usr/bin/env python3
"""Extract detail from Arakawa SUUMO listings"""

import json
import re
import time
import requests
from bs4 import BeautifulSoup
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def extract_detail(url):
    """Extract building details from SUUMO detail page"""
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.content, 'html.parser')
        text = soup.get_text()

        detail = {'url': url}

        # Building name from title
        title = soup.find('title')
        if title:
            parts = title.get_text().split('·')
            if parts:
                detail['name'] = parts[0].strip()

        # Price: "XXXX万"
        price_match = re.search(r'([\d,]+)\s*万', text)
        if price_match:
            try:
                price_yen = int(price_match.group(1).replace(',', '')) * 10000
                detail['price_yen'] = price_yen
                detail['price_str'] = f"¥{price_yen//10000}万"
            except:
                pass

        # Size: "XXm²" or "XX.Xm²"
        size_match = re.search(r'([\d.]+)\s*(?:m[²2m]|㎡)', text)
        if size_match:
            try:
                detail['size_m2'] = float(size_match.group(1))
                detail['size_str'] = f"{size_match.group(1)}m²"
            except:
                pass

        # Layout: "NLDKexperienced" or "NDK"
        layout_match = re.search(r'(\d+S?LDK|\d+DK)', text)
        if layout_match:
            detail['layout'] = layout_match.group(1)

        # Year: "YYYY年"
        year_match = re.search(r'(19|20)(\d{2})\s*年', text)
        if year_match:
            year_str = year_match.group(0)
            try:
                detail['year'] = year_str.replace('年', '').strip()
            except:
                detail['year'] = '?'

        # Floor: "NF" or "N階"
        floor_match = re.search(r'(\d+)\s*(?:階|F)(?:/\d+)?', text)
        if floor_match:
            detail['floor'] = f"{floor_match.group(1)}F"

        # Walk: "N分"
        walk_match = re.search(r'([^分\d]*?)(\d+)\s*分', text)
        if walk_match:
            detail['walk'] = f"{walk_match.group(2)}min"
            detail['station'] = walk_match.group(1).strip()

        # Monthly fees: "YYYY円" or "YYYY/月"
        fees_match = re.search(r'([\d,]+)\s*(?:円|/月)', text)
        if fees_match:
            try:
                fees_yen = int(fees_match.group(1).replace(',', ''))
                detail['fees_yen'] = fees_yen
                detail['fees_str'] = f"¥{fees_yen//1000}k" if fees_yen >= 1000 else f"¥{fees_yen}"
            except:
                pass

        # Direction: "南", "東", "西", "北", "南東", etc.
        for direction in ['南東', '南西', '北東', '北西', '南', '東', '西', '北']:
            if direction in text:
                detail['direction'] = direction
                break

        # Ownership: look for "権利" keywords
        if '権' in text or '借地' in text:
            detail['ownership'] = 'Leasehold'
        else:
            detail['ownership'] = 'Freehold'

        return detail if 'name' in detail else None

    except Exception as e:
        return None

if __name__ == '__main__':
    # Load URLs
    with open(r'C:\Users\zakat\Desktop\apartment\arakawa_listings_quick.json', 'r', encoding='utf-8') as f:
        listings = json.load(f)

    print(f"Processing {len(listings)} Arakawa listings...")
    results = []

    for i, listing in enumerate(listings, 1):
        url = listing['url']
        detail = extract_detail(url)

        if detail:
            results.append(detail)
            building_name = detail.get('name', '?')[:30]
            price = detail.get('price_str', '?')
            size = detail.get('size_str', '?')
            print(f"  [{i}/31] ✓ {building_name} | {price} | {size}")
        else:
            print(f"  [{i}/31] ✗ Failed to extract")

        time.sleep(0.3)

    # Save results
    with open(r'C:\Users\zakat\Desktop\apartment\arakawa_details.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Extracted {len(results)}/31 listings")
    print("Saved to arakawa_details.json")
