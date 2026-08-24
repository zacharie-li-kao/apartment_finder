#!/usr/bin/env python3
"""Debug version - check extraction"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import sys

# Fix encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# Fetch Itabashi page 1
url = "https://www.nomu.com/mansion/area_tokyo/13119/?pager_page=1"
print(f"Fetching: {url}\n")

resp = session.get(url, timeout=10)
resp.encoding = 'utf-8'
soup = BeautifulSoup(resp.text, 'html.parser')
links = soup.find_all('a', href=re.compile(r'/mansion/id/'))

print(f"Found {len(links)} links\n")

# Get first 3 listings
for i, link in enumerate(links[:3]):
    name = link.get_text(strip=True)
    detail_url = urljoin('https://www.nomu.com', link.get('href', ''))

    print(f"\n{i+1}. {name}")
    print(f"   URL: {detail_url}")

    # Fetch detail page
    try:
        detail_resp = session.get(detail_url, timeout=10)
        detail_resp.encoding = 'utf-8'
        text = detail_resp.text

        # Extract key fields
        price_m = re.search(r'(\d{1,2},?\d{3}|\d{1,4})\s*万', text)
        size_m = re.search(r'(\d+\.?\d*)\s*m[²m2]', text)
        year_m = re.search(r'(19|20)(\d{2})\s*年', text)
        walk_m = re.search(r'(\d+)\s*分', text)
        floor_m = re.search(r'(\d+)\s*(?:階|F)', text)
        layout_m = re.search(r'([1-5])[LDK]+', text)

        print(f"   Price: {price_m.group(1) if price_m else 'N/A'} 万")
        print(f"   Size: {size_m.group(1) if size_m else 'N/A'}m²")
        print(f"   Year: {year_m.group(0) if year_m else 'N/A'}")
        print(f"   Walk: {walk_m.group(1) if walk_m else 'N/A'}分")
        print(f"   Floor: {floor_m.group(1) if floor_m else 'N/A'}F")
        print(f"   Layout: {layout_m.group(0) if layout_m else 'N/A'}")

        # Check filters
        price_yen = int(price_m.group(1).replace(',', '')) * 10_000 if price_m else 0
        size_m2 = float(size_m.group(1)) if size_m else 0
        year = int(year_m.group(1) + year_m.group(2)) if year_m else 0
        walk_min = int(walk_m.group(1)) if walk_m else 0
        floor = int(floor_m.group(1)) if floor_m else 0

        print(f"\n   Filters:")
        print(f"     Price in range (1.5M-40M): {1_500_000 <= price_yen <= 40_000_000}")
        print(f"     Size >= 30m²: {size_m2 >= 30}")
        print(f"     Year >= 1982: {year >= 1982}")
        print(f"     Walk <= 15: {walk_min <= 15 if walk_min > 0 else 'N/A'}")
        print(f"     Floor >= 2: {floor >= 2}")

    except Exception as e:
        print(f"   Error: {e}")

print("\n" + "="*60)
print("Debug complete")
