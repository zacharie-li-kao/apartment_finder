#!/usr/bin/env python3
"""
Comprehensive NOMU/Yahoo scraper: All wards, all pages, extract details, filter, deduplicate.
"""

import requests
from bs4 import BeautifulSoup
import re
import sys
from urllib.parse import urljoin
import time
import concurrent.futures
from typing import Dict, List

# Configuration
NOMU_WARDS = {
    'Sumida': 13107,
    'Koto': 13108,
    'Itabashi': 13119,
    'Katsushika': 13122,
    'Chuo': 13102,
    'Minato': 13103,
    'Setagaya': 13112,
    'Nakano': 13114,
    'Ota': 13111,
    'Nerima': 13120,
    'Kita': 13117,
    'Arakawa': 13118,
}

# Load existing listings
existing_listings = set()
try:
    with open('existing_listings.txt', 'r', encoding='utf-8') as f:
        existing_listings = set(line.strip() for line in f if line.strip())
    print(f"Loaded {len(existing_listings)} existing listings for dedup\n")
except Exception as e:
    print(f"Warning: {e}\n")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def scrape_nomu_ward_all_pages(ward_name: str, ward_code: int) -> List[Dict]:
    """Scrape all pages of NOMU for a ward."""
    listings = []
    page = 1
    max_pages = 100  # Safety limit

    while page <= max_pages:
        offset = (page - 1) * 20
        url = f"https://www.nomu.com/mansion/SearchList/?wide=0&area_id[]={ward_code}&type=area&start={offset}"

        try:
            print(f"  {ward_name} page {page}...", end=' ', flush=True)
            resp = session.get(url, timeout=10)
            resp.encoding = 'utf-8'

            if resp.status_code != 200:
                print(f"Status {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'/mansion/id/'))

            if not links:
                print("No listings")
                break

            new_count = 0
            for link in links:
                name = link.get_text(strip=True)
                href = link.get('href', '')

                if name and '/mansion/id/' in href and name not in existing_listings and len(name) > 2:
                    listing_dict = {
                        'name': name,
                        'url': urljoin('https://www.nomu.com', href),
                        'ward': ward_name,
                        'source': 'NOMU',
                    }
                    listings.append(listing_dict)
                    new_count += 1

            print(f"Found {new_count}")
            page += 1
            time.sleep(0.5)

        except Exception as e:
            print(f"Error: {e}")
            break

    return listings

def main():
    print("=" * 80)
    print("COMPREHENSIVE NOMU SCRAPER - ALL WARDS")
    print("=" * 80)
    print()

    all_listings = []

    # Scrape each ward
    for ward_name, ward_code in sorted(NOMU_WARDS.items()):
        print(f"{ward_name}:")
        ward_listings = scrape_nomu_ward_all_pages(ward_name, ward_code)
        all_listings.extend(ward_listings)
        print(f"  Total for {ward_name}: {len(ward_listings)}")
        print()

    print("=" * 80)
    print(f"SUMMARY: Found {len(all_listings)} new listings across all wards")
    print("=" * 80)
    print()

    # Deduplicate by URL
    seen_urls = set()
    deduplicated = []
    for listing in all_listings:
        if listing['url'] not in seen_urls:
            deduplicated.append(listing)
            seen_urls.add(listing['url'])

    print(f"After URL dedup: {len(deduplicated)} listings")
    print()

    # Save results
    print("Saving results...")
    with open('NOMU_ALL_WARDS_RESULTS.txt', 'w', encoding='utf-8') as f:
        f.write("NEW LISTINGS FROM NOMU.COM\n")
        f.write("=" * 100 + "\n")
        f.write("Ward | Name | URL | Source\n")
        f.write("=" * 100 + "\n\n")

        for listing in sorted(deduplicated, key=lambda x: x['ward']):
            f.write(f"{listing['ward']} | {listing['name']} | {listing['url']} | {listing['source']}\n")

    print(f"Results saved to NOMU_ALL_WARDS_RESULTS.txt")
    print(f"File contains {len(deduplicated)} new listing URLs for manual review")
    print()
    print("Next step: Fetch detail pages to extract price, size, floor, year, fees, direction")
    print("Then filter by criteria and output in final format")

if __name__ == '__main__':
    main()
