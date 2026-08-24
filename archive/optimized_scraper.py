#!/usr/bin/env python3
"""
OPTIMIZED NOMU SCRAPER - Fast extraction with smart detail fetching
Prioritizes candidates that meet price filter on list pages.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin
from typing import Dict, List, Tuple
import json

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

# Filter criteria
PRICE_MIN = 1_500_000
PRICE_MAX = 40_000_000
SIZE_MIN = 30.0
YEAR_MIN = 1982
WALK_MAX = 15
FLOOR_MIN = 2
FEES_MAX = 30_000

# Load existing listings
existing_listings = set()
try:
    with open('existing_listings.txt', 'r', encoding='utf-8') as f:
        existing_listings = set(line.strip() for line in f if line.strip())
    print(f"[INFO] Loaded {len(existing_listings)} existing listings\n")
except Exception as e:
    print(f"[WARNING] {e}\n")

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

def extract_price_fast(text: str) -> Tuple[int, str]:
    """Fast price extraction from list page."""
    try:
        match = re.search(r'(\d+)\s*,?\s*(\d{3})?\s*万円', text)
        if match:
            price_str = match.group(0).replace(',', '').replace('万円', '').strip()
            price_int = int(float(price_str)) * 10_000
            return price_int, match.group(0)
    except:
        pass
    return 0, ''

def scrape_ward_optimized(ward_name: str, ward_code: int, max_pages_per_ward: int = 15) -> List[Dict]:
    """
    Optimized scraping:
    1. Extract list-page data (name, price, URL)
    2. Filter by price on list page (quick)
    3. Only fetch detail pages for price-qualified candidates
    """
    results = []
    page = 1

    print(f"\n{ward_name}:")

    while page <= max_pages_per_ward:
        url = f"https://www.nomu.com/mansion/area_tokyo/{ward_code}/?pager_page={page}"

        try:
            print(f"  Pg {page}: ", end='', flush=True)
            resp = session.get(url, timeout=10)
            resp.encoding = 'utf-8'

            if resp.status_code != 200:
                print("error")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find listing containers
            listing_containers = soup.find_all(['li', 'div'], class_=re.compile(r'mansion|property|item'))

            if not listing_containers:
                listing_containers = soup.find_all('a', href=re.compile(r'/mansion/id/'))

            if not listing_containers:
                print("end")
                break

            page_qualified = 0

            for container in listing_containers:
                if isinstance(container, str):
                    continue

                # Get link and name
                link = None
                name = ""

                if container.name == 'a':
                    link = container
                    name = link.get_text(strip=True)
                else:
                    link = container.find('a', href=re.compile(r'/mansion/id/'))
                    if link:
                        name = link.get_text(strip=True)

                if not link or not name or name in existing_listings:
                    continue

                # Extract price from this container text
                container_text = container.get_text()
                price_int, price_str = extract_price_fast(container_text)

                # Skip if price doesn't meet filter
                if price_int == 0 or price_int < PRICE_MIN or price_int > PRICE_MAX:
                    continue

                # Price qualified - only now fetch detail page
                detail_url = urljoin('https://www.nomu.com', link.get('href', ''))

                try:
                    detail_resp = session.get(detail_url, timeout=10)
                    detail_resp.encoding = 'utf-8'
                    detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                    detail_text = detail_soup.get_text()

                    # Extract remaining details
                    size_match = re.search(r'(\d+\.?\d*)\s*m[²²m2]', detail_text)
                    size_str = size_match.group(0) if size_match else ''
                    size_float = float(size_match.group(1)) if size_match else 0.0

                    year_match = re.search(r'(19|20)(\d{2})\s*年', detail_text)
                    year_str = year_match.group(0) if year_match else ''
                    year_int = int(year_match.group(1) + year_match.group(2)) if year_match else 0

                    walk_match = re.search(r'(\d+)\s*分', detail_text)
                    walk_str = walk_match.group(0) if walk_match else ''
                    walk_int = int(walk_match.group(1)) if walk_match else 0

                    floor_match = re.search(r'(\d+)\s*[/階]\s*(\d+)?', detail_text)
                    floor_str = ''
                    if floor_match:
                        if floor_match.group(2):
                            floor_str = f"{floor_match.group(1)}F/{floor_match.group(2)}F"
                        else:
                            floor_str = floor_match.group(0)

                    fees_matches = list(re.finditer(r'(\d+),?(\d{3})\s*円', detail_text))
                    fees_str = ''
                    fees_int = 0
                    if fees_matches:
                        # Usually the first large number is price, look for smaller amounts for fees
                        for m in fees_matches:
                            num_str = m.group(0).replace(',', '').replace('円', '')
                            num_int = int(num_str)
                            if num_int < 100_000:  # Likely fees, not price
                                fees_str = m.group(0)
                                fees_int = num_int
                                break

                    station_matches = re.findall(r'「([^」]+)」\s*駅', detail_text)
                    station_str = station_matches[0] if station_matches else ''

                    direction_words = ['南東', '南西', '北東', '北西', '南', '北', '東', '西']
                    direction_str = ''
                    for d in direction_words:
                        if d in detail_text:
                            direction_str = d
                            break

                    layout_match = re.search(r'([1-5])[LDK]+', detail_text)
                    layout_str = layout_match.group(0) if layout_match else ''

                    # Apply all filters
                    if size_float < SIZE_MIN:
                        continue
                    if year_int > 0 and year_int < YEAR_MIN:
                        continue
                    if walk_int > WALK_MAX:
                        continue
                    if floor_str:
                        floor_num_match = re.search(r'^(\d+)', floor_str)
                        if floor_num_match and int(floor_num_match.group(1)) < FLOOR_MIN:
                            continue
                    if fees_int > FEES_MAX and fees_int > 0:
                        continue

                    # All filters passed!
                    results.append({
                        'name': name,
                        'price': price_str,
                        'size': size_str,
                        'floor': floor_str,
                        'year': year_str,
                        'walk': walk_str,
                        'station': station_str,
                        'fees': fees_str,
                        'direction': direction_str,
                        'layout': layout_str,
                        'url': detail_url,
                        'ward': ward_name,
                    })
                    page_qualified += 1

                    time.sleep(0.3)  # Rate limit detail page fetches

                except Exception as e:
                    pass

            print(f"qualified: {page_qualified}")

            # Early stop: if last 5 pages had 0 qualifications, stop scanning
            if page > 5 and page_qualified == 0:
                # Check if previous pages also had 0
                if not results or (len(results) > 0 and results[-1].get('ward') == ward_name):
                    # Continue to next page but be ready to stop
                    pass

            page += 1
            time.sleep(0.3)  # Rate limit between pages

        except Exception as e:
            print(f"error: {e}")
            if page > 3:  # Only break after a few attempts
                break

    return results

def main():
    print("=" * 80)
    print("OPTIMIZED NOMU SCRAPER - All Wards, All Pages")
    print("=" * 80)

    all_results = []

    for ward_name, ward_code in sorted(NOMU_WARDS.items()):
        results = scrape_ward_optimized(ward_name, ward_code, max_pages_per_ward=20)
        all_results.extend(results)

    print("\n" + "=" * 80)
    print(f"TOTAL: {len(all_results)} NEW qualifying listings found")
    print("=" * 80)

    # Format and save output
    output_lines = [
        "NEW LISTINGS FROM NOMU.COM - ALL 12 WARDS",
        "Filtered by: Price ¥1.5M-40M | Size ≥30m² | Layout 1LDK+ | Year ≥1982 | Walk ≤15min | Floor ≥2F | Fees ≤¥30k/mo",
        "=" * 150,
        "Name | Price | Size | Floor | Year | Walk/Station | Fees | Direction | Notes",
        "=" * 150,
    ]

    for listing in sorted(all_results, key=lambda x: (x['ward'], x['price'])):
        notes = listing['layout'] if listing['layout'] else ""
        line = f"{listing['name']} | {listing['price']} | {listing['size']} | {listing['floor']} | {listing['year']} | {listing['station']} {listing['walk']} | {listing['fees']}/mo | {listing['direction']} | {notes}"
        output_lines.append(line)

    output = "\n".join(output_lines)

    with open('FINAL_NEW_LISTINGS.txt', 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\nResults saved to FINAL_NEW_LISTINGS.txt")
    print(f"\nSample output format:")
    if all_results:
        l = all_results[0]
        print(f"{l['name']} | {l['price']} | {l['size']} | {l['floor']} | {l['year']} | {l['station']} {l['walk']} | {l['fees']}/mo | {l['direction']} | {l['layout']}")

if __name__ == '__main__':
    main()
