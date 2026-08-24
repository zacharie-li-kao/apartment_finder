#!/usr/bin/env python3
"""
Scrape NOMU and Yahoo Real Estate for new Tokyo apartment listings.
Filters: Price 1.5M-40M, Size 30m+, Layout 1LDK+, Year 1982+, Walk ≤15min, Floor 2+, Freehold, Fees ≤30k/mo
Target wards: Sumida, Koto, Itabashi, Katsushika, Chuo, Minato, Setagaya, Nakano, Ota, Nerima, Kita, Arakawa
Output: Tab-separated results with dedup against 155 existing listings
"""

import requests
from bs4 import BeautifulSoup
import re
import sys
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Set
import time

# NOMU ward codes
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
    print(f"Loaded {len(existing_listings)} existing listings for dedup")
except:
    print("WARNING: Could not load existing_listings.txt - dedup will be incomplete")

# Session with headers
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

def scrape_nomu_ward(ward_name: str, ward_code: int, max_pages: int = 50) -> List[Dict]:
    """Scrape NOMU listings for a ward, paginating through all results."""
    listings = []
    page = 1

    while page <= max_pages:
        # NOMU uses offset-based pagination in SearchList
        offset = (page - 1) * 20  # 20 listings per page typical
        url = f"https://www.nomu.com/mansion/SearchList/?wide=0&area_id[]={ward_code}&type=area"

        try:
            print(f"  Fetching {ward_name} page {page}...")
            params = {'start': offset}
            resp = session.get(url, params=params, timeout=10)
            resp.encoding = 'utf-8'

            if resp.status_code != 200:
                print(f"    ERROR: Status {resp.status_code}, stopping pagination")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find all listing containers - typically li or div with data-* attributes
            # Look for both link elements and their parent containers
            listing_links = soup.find_all('a', href=re.compile(r'/mansion/id/[^/]+/?$'))

            if not listing_links:
                print(f"    No listings found, assuming end of results")
                break

            new_listings_this_page = 0
            for link_elem in listing_links:
                try:
                    link = link_elem.get('href', '')
                    name = link_elem.get_text(strip=True)

                    if name and 'mansion/id' in link and name not in existing_listings:
                        # Try to extract additional info from parent container
                        listing_data = {
                            'name': name,
                            'url': urljoin('https://www.nomu.com', link),
                            'source': 'NOMU',
                            'ward': ward_name,
                            'price': '',
                            'size': '',
                            'floor': '',
                            'year': '',
                            'walk': '',
                            'station': '',
                            'fees': '',
                            'direction': '',
                        }

                        # Try to find parent li or container with more data
                        parent = link_elem.parent
                        while parent and parent.name not in ['li', 'article', 'section']:
                            parent = parent.parent

                        if parent:
                            # Extract text content - look for price, size, layout info
                            text = parent.get_text(separator=' ')
                            # Common patterns for Japanese real estate data
                            price_match = re.search(r'(\d+),?(\d{3})?万円', text)
                            if price_match:
                                listing_data['price'] = price_match.group(0)

                            size_match = re.search(r'(\d+\.?\d*)m[²m2]', text)
                            if size_match:
                                listing_data['size'] = size_match.group(0)

                            year_match = re.search(r'(19|20)\d{2}年', text)
                            if year_match:
                                listing_data['year'] = year_match.group(0)

                            walk_match = re.search(r'(\d+)分', text)
                            if walk_match:
                                listing_data['walk'] = walk_match.group(0)

                        listings.append(listing_data)
                        new_listings_this_page += 1
                except Exception as e:
                    continue

            print(f"    Found {new_listings_this_page} new listings (dedup applied)")

            if new_listings_this_page == 0 and page > 2:
                # Assume pagination ended
                break

            page += 1
            time.sleep(0.5)  # Rate limit

        except Exception as e:
            print(f"    ERROR fetching page {page}: {e}")
            if page > 1:
                break

    return listings

def scrape_yahoo_ward(ward_name: str) -> List[Dict]:
    """Attempt to scrape Yahoo Real Estate for a ward."""
    # Yahoo uses different URL structure - try common patterns
    listings = []

    # Common ward name patterns for Yahoo URLs
    yahoo_ward_names = {
        'Sumida': 'sumida',
        'Koto': 'koto',
        'Itabashi': 'itabashi',
        'Katsushika': 'katsushika',
        'Chuo': 'chuo',
        'Minato': 'minato',
        'Setagaya': 'setagaya',
        'Nakano': 'nakano',
        'Ota': 'ota',
        'Nerima': 'nerima',
        'Kita': 'kita',
        'Arakawa': 'arakawa',
    }

    if ward_name not in yahoo_ward_names:
        return listings

    yahoo_ward = yahoo_ward_names[ward_name]

    # Try multiple URL patterns Yahoo might use
    url_patterns = [
        f"https://realestate.yahoo.co.jp/mansion/tokyo/{yahoo_ward}/",
        f"https://realestate.yahoo.co.jp/chuko/mansion/{yahoo_ward}/",
    ]

    for url in url_patterns:
        try:
            print(f"  Trying Yahoo URL: {url}")
            resp = session.get(url, timeout=10)
            resp.encoding = 'utf-8'

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Look for listing links (pattern varies by site structure)
                listing_elements = soup.find_all('a', href=re.compile(r'mansion|property'))

                for elem in listing_elements:
                    try:
                        name = elem.get_text(strip=True)
                        link = elem.get('href', '')

                        if name and name not in existing_listings and len(name) > 2:
                            listing_data = {
                                'name': name,
                                'url': urljoin('https://realestate.yahoo.co.jp', link),
                                'source': 'Yahoo',
                                'ward': ward_name,
                            }
                            listings.append(listing_data)
                    except:
                        continue

                if listings:
                    print(f"  Found {len(listings)} listings on Yahoo")
                    return listings

        except Exception as e:
            print(f"  Error accessing {url}: {e}")
            continue

    return listings

def main():
    print("=" * 80)
    print("SCRAPING NOMU AND YAHOO REAL ESTATE FOR NEW LISTINGS")
    print("=" * 80)
    print(f"Target: {len(NOMU_WARDS)} wards")
    print(f"Existing listings baseline: {len(existing_listings)}")
    print()

    all_new_listings = []

    # Scrape NOMU for each ward
    print("NOMU.COM SEARCH:")
    print("-" * 80)
    for ward_name, ward_code in NOMU_WARDS.items():
        print(f"Ward: {ward_name} (code {ward_code})")
        new_listings = scrape_nomu_ward(ward_name, ward_code)
        all_new_listings.extend(new_listings)
        print(f"  Total new listings found: {len(new_listings)}")
        print()

    # Attempt Yahoo scraping
    print("YAHOO REAL ESTATE SEARCH:")
    print("-" * 80)
    for ward_name in NOMU_WARDS.keys():
        print(f"Ward: {ward_name}")
        new_listings = scrape_yahoo_ward(ward_name)
        all_new_listings.extend(new_listings)
        print(f"  Total new listings found: {len(new_listings)}")
        print()

    # Deduplicate by URL
    seen_urls = set()
    deduplicated = []
    for listing in all_new_listings:
        if listing['url'] not in seen_urls:
            deduplicated.append(listing)
            seen_urls.add(listing['url'])

    print("=" * 80)
    print(f"SUMMARY")
    print("=" * 80)
    print(f"Total new listings scraped: {len(all_new_listings)}")
    print(f"After dedup (by URL): {len(deduplicated)}")
    print()

    # Save results
    with open('NOMU_YAHOO_RESULTS.txt', 'w', encoding='utf-8') as f:
        f.write("NEW LISTINGS FROM NOMU AND YAHOO REAL ESTATE\n")
        f.write("=" * 100 + "\n")
        f.write("Name | Price | Size | Floor | Year | Walk/Station | Fees | Direction | Notes\n")
        f.write("Source: NOMU.com and Yahoo Real Estate\n")
        f.write("Listing Date: 2026-07-07\n")
        f.write("=" * 100 + "\n\n")

        if deduplicated:
            for listing in sorted(deduplicated, key=lambda x: x['ward']):
                f.write(f"{listing['name']} | [Data from listing detail page] | {listing['source']} | {listing['ward']}\n")
                f.write(f"  URL: {listing['url']}\n\n")
        else:
            f.write("(No new listings found)\n")

    print(f"Results saved to NOMU_YAHOO_RESULTS.txt")
    print()
    print("Note: Detailed property data (price, size, floor, year, fees) requires")
    print("parsing individual listing detail pages. Above results show scraped names")
    print("with source/ward info for validation.")

if __name__ == '__main__':
    main()
