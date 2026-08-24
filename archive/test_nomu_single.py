#!/usr/bin/env python3
"""Quick test of NOMU scraper on single ward"""

import requests
from bs4 import BeautifulSoup
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Test fetching a page
url = "https://www.nomu.com/mansion/area_tokyo/13107/?pager_page=1"
print(f"Testing: {url}")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

try:
    resp = session.get(url, timeout=10)
    print(f"Status: {resp.status_code}")

    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find listing links
        links = soup.find_all('a', href=re.compile(r'/mansion/id/'))
        print(f"Found {len(links)} listing links")

        if links:
            print("\nFirst 3 links:")
            for i, link in enumerate(links[:3]):
                name = link.get_text(strip=True)
                href = link.get('href', '')
                print(f"  {i+1}. {name} -> {href}")

        # Check for pagination
        pager = soup.find('a', string=re.compile(r'次'))
        if pager:
            print("\nNext page link found: Yes")
        else:
            print("\nNext page link found: No")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
