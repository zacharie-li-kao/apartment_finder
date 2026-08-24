#!/usr/bin/env python3
"""Inspect NOMU detail page structure"""

import requests
from bs4 import BeautifulSoup
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

# Check a specific listing
url = "https://www.nomu.com/mansion/id/F93C4013/"
print(f"URL: {url}\n")

resp = session.get(url, timeout=10)
resp.encoding = 'utf-8'
text = resp.text

# Look for price patterns - different formats
print("=== SEARCHING FOR PRICES ===")

patterns = [
    (r'(\d{1,3}),?(\d{3})\s*万円', 'XXXX万円'),
    (r'価格.*?(\d{1,3},?\d{1,3}(?:,?\d{3})?)\s*円', '価格 XXX円'),
    (r'(\d+)\s*万\s*円', 'XXXX万 円'),
    (r'(\d{2})\s*万', 'XX万 (百万単位)'),
]

for pattern, desc in patterns:
    matches = re.findall(pattern, text)
    if matches:
        print(f"{desc}: {matches[:5]}")

# Look at raw text around price keywords
print("\n=== TEXT AROUND 'ザ·' ===")
for m in re.finditer(r'([0-9, ]{5,20}万円)', text):
    start = max(0, m.start() - 30)
    end = min(len(text), m.end() + 30)
    snippet = text[start:end].replace('\n', ' ')[:80]
    print(f"  ...{snippet}...")

# Try finding price in title or structured data
print("\n=== CHECKING TITLE ===")
title_match = re.search(r'<title>([^<]+)</title>', text)
if title_match:
    print(f"Title: {title_match.group(1)}")

# Look for JSON/structured data
print("\n=== CHECKING FOR STRUCTURED DATA ===")
if 'price' in text.lower():
    # Find context around 'price'
    indices = [m.start() for m in re.finditer(r'price', text, re.IGNORECASE)]
    for idx in indices[:3]:
        start = max(0, idx - 40)
        end = min(len(text), idx + 80)
        snippet = text[start:end].replace('\n', ' ')
        if any(c.isdigit() for c in snippet):
            print(f"  ...{snippet}...")

print("\n=== SEARCHING FOR ANY LARGE NUMBERS ===")
large_nums = re.findall(r'\d{7,9}(?:\s*万)?\s*円', text)
if large_nums:
    print(f"Large numbers (7-9 digits): {large_nums[:5]}")

large_nums2 = re.findall(r'(\d{4,5})\s*万円', text)
if large_nums2:
    print(f"万円 format: {large_nums2[:5]}")
