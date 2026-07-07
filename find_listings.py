#!/usr/bin/env python3
"""Find actual listing elements in NOMU HTML"""

import requests
from bs4 import BeautifulSoup
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

url = "https://www.nomu.com/mansion/area_tokyo/13107/?pager_page=1"
resp = session.get(url, timeout=10)
soup = BeautifulSoup(resp.content, 'html.parser')

# Look for listing price patterns (should appear multiple times on page)
html_text = str(soup)
prices = re.findall(r'(\d{1,2},\d{3})万', html_text)
print(f"Found {len(prices)} prices on page:")
for i, price in enumerate(prices[:10]):
    print(f"  {price}万")

print("\n=== Looking for price containers ===")
# Find elements containing price text
for elem in soup.find_all(string=re.compile(r'\d{1,2},\d{3}万')):
    parent = elem.find_parent()
    if parent:
        print(f"Tag: {parent.name}, Class: {parent.get('class')}, Text: {elem[:50]}")
        # Look at parent structure
        grandparent = parent.find_parent()
        if grandparent:
            print(f"  Parent: {grandparent.name} class={grandparent.get('class')}")
            # Find siblings that might be listing name
            for sibling in grandparent.find_all(recursive=False):
                text = sibling.get_text(strip=True)[:100]
                if text:
                    print(f"    Sibling: {sibling.name} text={text}")

print("\n=== Looking for div with Japanese building names ===")
# Search for building names (Japanese characters followed by numbers)
for elem in soup.find_all('a', href=True):
    text = elem.get_text(strip=True)
    href = elem.get('href')
    # Check if looks like building name (has Japanese chars and mansion id in URL)
    if re.search(r'[ァ-ヴー一-龯]', text) and 'mansion' in href:
        print(f"  {text[:50]} => {href}")
        if len(text) > 50:  # Stop after finding a few
            break

print("\n=== Checking common listing container classes ===")
for class_name in ['item', 'house', 'property', 'mansion', 'card', 'list', 'result']:
    elements = soup.find_all(class_=re.compile(class_name, re.IGNORECASE))
    print(f"Elements with '{class_name}': {len(elements)}")
