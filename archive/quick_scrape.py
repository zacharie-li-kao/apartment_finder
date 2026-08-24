#!/usr/bin/env python3
"""Quick scraper to test NOMU with just Sumida ward - fast feedback."""

import requests
from bs4 import BeautifulSoup
import re
import sys
from urllib.parse import urljoin
import time

# Load existing listings
existing_listings = set()
try:
    with open('existing_listings.txt', 'r', encoding='utf-8') as f:
        existing_listings = set(line.strip() for line in f if line.strip())
    print(f"Loaded {len(existing_listings)} existing listings for dedup\n")
except:
    print("WARNING: Could not load existing_listings.txt\n")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def scrape_nomu_ward(ward_name: str, ward_code: int) -> list:
    """Scrape just first 3 pages of NOMU for quick feedback."""
    listings = []

    for page in range(1, 4):  # Just 3 pages for testing
        offset = (page - 1) * 20
        url = f"https://www.nomu.com/mansion/SearchList/?wide=0&area_id[]={ward_code}&type=area&start={offset}"

        try:
            print(f"Fetching {ward_name} page {page}...")
            resp = session.get(url, timeout=15)
            resp.encoding = 'utf-8'

            if resp.status_code != 200:
                print(f"  Status {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find listing links
            links = soup.find_all('a', href=re.compile(r'/mansion/id/'))
            print(f"  Found {len(links)} links on this page")

            if not links:
                print(f"  No listings, stopping")
                break

            new_count = 0
            for link in links:
                name = link.get_text(strip=True)
                href = link.get('href', '')

                if name and '/mansion/id/' in href and name not in existing_listings and len(name) > 3:
                    listings.append({
                        'name': name,
                        'url': urljoin('https://www.nomu.com', href),
                    })
                    new_count += 1

            print(f"  Found {new_count} NEW listings on this page")
            print()
            time.sleep(1)

        except Exception as e:
            print(f"  ERROR: {e}")
            break

    return listings

# Test with Sumida only
print("=" * 60)
print("TESTING NOMU SCRAPER - Sumida Ward Only (First 3 Pages)")
print("=" * 60 + "\n")

results = scrape_nomu_ward('Sumida', 13107)

print("=" * 60)
print(f"RESULTS: Found {len(results)} new listings")
print("=" * 60)

if results:
    # Save for inspection
    with open('quick_scrape_results.txt', 'w', encoding='utf-8') as f:
        for listing in results:
            f.write(f"{listing['name']}\t{listing['url']}\n")

    print(f"\nResults saved to quick_scrape_results.txt")
    print(f"Sample (first 10):")
    for i, listing in enumerate(results[:10], 1):
        try:
            print(f"  {i}. {listing['name']}")
        except:
            print(f"  {i}. [Japanese name - see file]")
else:
    print("\nNo new listings found (all dedup'd against existing)")
