#!/usr/bin/env python3
"""Inspect NOMU HTML structure"""

import requests
from bs4 import BeautifulSoup
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

url = "https://www.nomu.com/mansion/id/F93C4013/"
print(f"URL: {url}\n")

resp = session.get(url, timeout=10)
resp.encoding = 'utf-8'
soup = BeautifulSoup(resp.text, 'html.parser')

# Find price element
print("=== PRICE ELEMENT ===")
price_elem = soup.find(class_='item_price')
if price_elem:
    print(f"Found: {price_elem}")
    num = price_elem.find(class_='num')
    if num:
        print(f"Price number: {num.get_text()}")
        unit = price_elem.find(class_='unit')
        if unit:
            print(f"Unit: {unit.get_text()}")

# Find size element
print("\n=== SIZE ELEMENT ===")
size_elems = soup.find_all(string=re.compile(r'\d+\.?\d*\s*m[²m2]'))
for elem in size_elems[:3]:
    print(f"Found: {elem}")

# Find year element
print("\n=== YEAR ELEMENT ===")
year_elems = soup.find_all(string=re.compile(r'(19|20)\d{2}\s*年'))
for elem in year_elems[:3]:
    print(f"Found: {elem}")

# Find layout element
print("\n=== LAYOUT ELEMENT ===")
layout_elems = soup.find_all(string=re.compile(r'[0-9][LDK]+'))
for elem in layout_elems[:3]:
    print(f"Found: {elem}")

# Find floor element
print("\n=== FLOOR ELEMENT ===")
floor_elems = soup.find_all(string=re.compile(r'(\d+)\s*(?:階|F)'))
for elem in floor_elems[:3]:
    print(f"Found: {elem}")

# Find walk time
print("\n=== WALK TIME ===")
walk_elems = soup.find_all(string=re.compile(r'(\d+)\s*分'))
for elem in walk_elems[:5]:
    print(f"Found: {elem}")
