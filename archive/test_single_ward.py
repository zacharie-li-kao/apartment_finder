#!/usr/bin/env python3
"""Quick test of single ward scraping with new HTML parsing"""

import requests
from bs4 import BeautifulSoup
import re

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# Test Sumida ward (small)
url = "https://www.nomu.com/mansion/area_tokyo/13107/?pager_page=1"
print(f"Fetching: {url}")

resp = session.get(url, timeout=10)
print(f"Status: {resp.status_code}")
print(f"Content length: {len(resp.content)}")

soup = BeautifulSoup(resp.content, 'html.parser')

# Find all item_table elements
items = soup.find_all(class_='item_table')
print(f"\nFound {len(items)} listing items on page 1\n")

# Parse first few listings
for i, item in enumerate(items[:3]):
    print(f"=== Listing {i+1} ===")

    # Extract URL
    url_elem = item.find('a', href=True)
    detail_url = url_elem.get('href', '') if url_elem else None
    if detail_url and detail_url.startswith('/'):
        detail_url = 'https://www.nomu.com' + detail_url
    print(f"URL: {detail_url}")

    # Extract name
    name_elem = item.find(class_='item_title')
    name = name_elem.get_text(strip=True) if name_elem else None
    print(f"Name: {name}")

    # Extract price
    price_elem = item.find(class_='item_price')
    price_text = None
    if price_elem:
        price_span = price_elem.find('span', class_='num')
        if price_span:
            price_text = price_span.get_text(strip=True)
    print(f"Price: {price_text}")

    # Extract full text content
    content_text = item.get_text(' ', strip=True)
    print(f"Full text (first 300 chars): {content_text[:300]}")

    # Extract layout
    layout_match = re.search(r'(\d+(?:LDK|DK|R|L))', content_text)
    layout = layout_match.group(1) if layout_match else None
    print(f"Layout: {layout}")

    # Extract year
    year_match = re.search(r'([12][09]\d{2})', content_text)
    year = year_match.group(1) if year_match else None
    print(f"Year: {year}")

    # Extract walk time
    walk_match = re.search(r'(\d+)\s*(?:分|min)', content_text)
    walk = walk_match.group(1) if walk_match else None
    print(f"Walk: {walk}min")

    # Extract size
    size_match = re.search(r'(\d+\.?\d*)(?:\s*m²|㎡)', content_text)
    size = size_match.group(1) if size_match else None
    print(f"Size: {size}m2")

    print()
