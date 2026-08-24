#!/usr/bin/env python3
"""Debug NOMU HTML structure"""

import requests
from bs4 import BeautifulSoup
import re
import sys

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

url = "https://www.nomu.com/mansion/area_tokyo/13107/?pager_page=1"
print(f"Fetching: {url}")

resp = session.get(url, timeout=10)
print(f"Status: {resp.status_code}")

soup = BeautifulSoup(resp.content, 'html.parser')

# Find all item_table elements
items = soup.find_all(class_='item_table')
print(f"Found {len(items)} item_table elements\n")

if len(items) > 0:
    item = items[0]
    print("=== First listing raw HTML (first 1000 chars) ===")
    print(item.prettify()[:1000])
    print("\n=== Searching for elements ===")

    # Try different selector patterns
    print(f"Class 'item_title': {item.find(class_='item_title')}")
    print(f"Class 'item_price': {item.find(class_='item_price')}")
    print(f"Tag 'a' with href: {item.find('a', href=True)}")

    # Get all divs with data attributes
    divs_with_class = item.find_all(class_=True)
    print(f"\nAll elements with class (first 20):")
    for div in divs_with_class[:20]:
        print(f"  {div.name} class='{div.get('class')}' text='{div.get_text(strip=True)[:50]}'")

print("\n=== Checking for common patterns ===")
html_text = str(soup)
print(f"Contains 'mansion': {'mansion' in html_text.lower()}")
print(f"Contains 'item_': {'item_' in html_text}")
print(f"Contains '万': {'万' in html_text}")
