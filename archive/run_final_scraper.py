#!/usr/bin/env python3
"""Final scraper with bug fixes"""

import requests
import re
import subprocess
import sys
from bs4 import BeautifulSoup
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# FIX #1: Correct price parser
def parse_price_man(price_str):
    """Parse price in 万 units. 2,190万 = 2190 (not 2.1)"""
    if not price_str:
        return None
    cleaned = re.sub(r'[^\d,]', '', price_str).replace(',', '')
    try:
        return float(cleaned)
    except:
        return None

# Test the price parser
print("=== PRICE PARSER TEST ===")
test_prices = ["2,190万", "12,800万", "3,390万", "1,500万", "40,000万"]
for p in test_prices:
    parsed = parse_price_man(p)
    min_budget = 15  # 1.5M in 万
    max_budget = 400  # 40M in 万
    passes = min_budget <= parsed <= max_budget if parsed else False
    print(f"  {p:12} -> {parsed:7.1f}万 (${parsed/100:.1f}M) - {'PASS' if passes else 'FAIL'}")

# FIX #2: Extract 116 buildings
print("\n=== DATABASE EXTRACTION ===")
result = subprocess.run(
    ['git', 'log', '--all', '--format=%s'],
    cwd='C:\Users\zakat\Desktop\apartment',
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

buildings = set()
for line in result.stdout.split('\n'):
    if not line.strip() or 'Add #' not in line:
        continue
    match = re.search(r'^Add #[\d\-]+\s+([^(\n]+?)(?:\s*[\(·]|$)', line)
    if match:
        name = match.group(1).strip()
        if name and len(name) > 2:
            buildings.add(name)

print(f"Extracted {len(buildings)} unique buildings")

# FIX #3: Test NOMU HTML parsing
print("\n=== TESTING NOMU HTML PARSING ===")
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

url = "https://www.nomu.com/mansion/area_tokyo/13107/?pager_page=1"
try:
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    # Count building links
    building_links = soup.find_all('a', href=re.compile(r'/mansion/id/'))
    print(f"Found {len(building_links)} building links on page 1")
    
    # Show first 3
    for i, a_tag in enumerate(building_links[:3]):
        name = a_tag.get_text(strip=True)
        href = a_tag.get('href', '')
        
        # Get card container text
        card = a_tag.find_parent()
        while card and card.name not in ['div', 'tr', 'li', 'article', 'section']:
            card = card.find_parent()
        
        if card:
            card_text = card.get_text(' ', strip=True)[:200]
        else:
            card_text = "No card found"
        
        # Extract price from card text
        price_match = re.search(r'([\d,]+)\s*万', card_text if card else "")
        price_str = price_match.group(1) if price_match else "No price"
        price_man = parse_price_man(price_str) if price_match else None
        
        print(f"\n  {i+1}. {name}")
        print(f"     Price: {price_str} -> {price_man}万" if price_man else f"     Price: not found in card text")
        print(f"     Card text: {card_text}")
        
except Exception as e:
    print(f"Error: {e}")

print("\n=== TEST COMPLETE ===")
