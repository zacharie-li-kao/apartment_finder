#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("Fetching SUUMO Arakawa page 1...")
resp = requests.get('https://suumo.jp/ms/chuko/tokyo/sc_arakawa/?page=1', headers=headers, timeout=15)
print(f"Status: {resp.status_code}\n")

soup = BeautifulSoup(resp.content, 'html.parser')

# Try various patterns to find listing links
patterns = [
    r'/ms/chuko/tokyo/sc_.*/nc_\d+',
    r'/ms/chuko/tokyo/sc_arakawa/nc_\d+',
    r'nc_\d+',
    r'/ms/chuko',
]

print("Testing different link patterns:\n")
for pattern in patterns:
    links = soup.find_all('a', href=re.compile(pattern))
    print(f"Pattern: {pattern}")
    print(f"  Found: {len(links)} links")
    if links and len(links) > 0:
        print(f"  Sample: {links[0].get('href')}\n")
    else:
        print()

# Try finding all links
print("\nAll links containing 'nc_':")
all_links = soup.find_all('a', href=True)
nc_links = [link for link in all_links if 'nc_' in link.get('href', '')]
print(f"Found {len(nc_links)} links with 'nc_'")

if nc_links:
    print("\nFirst 10 nc_ links:")
    for i, link in enumerate(nc_links[:10]):
        href = link.get('href', '')
        print(f"  {i+1}. {href}")

# Check the structure of the page
print("\n\nPage structure analysis:")
print(f"Total <a> tags: {len(all_links)}")

# Look for property listings containers
divs_with_class = soup.find_all('div', class_=True)
print(f"Total <div> tags with class: {len(divs_with_class)}")

# Sample some class names
print("\nSample div classes (first 10 unique):")
classes = set()
for div in divs_with_class[:100]:
    div_class = div.get('class', [])
    if div_class:
        classes.add(' '.join(div_class))
    if len(classes) >= 10:
        break

for cls in list(classes)[:10]:
    print(f"  - {cls}")
