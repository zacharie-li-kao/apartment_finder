#!/usr/bin/env python3
"""
Comprehensive scraper for Rehouse Koto-ku listings
Fetches all 246 listings, applies filters, and checks detail pages for ownership info
"""

import requests
import json
import time
import sys
from typing import Optional, Dict, List, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Fix encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13108/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_page(page_num: int = 1) -> Optional[str]:
    """Fetch a page and return HTML content"""
    try:
        params = {} if page_num == 1 else {'page': page_num}
        response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        print(f"Error: Status {response.status_code} for page {page_num}")
        return None
    except Exception as e:
        print(f"Error fetching page {page_num}: {e}")
        return None

def parse_listings_from_html(html: str) -> List[Dict]:
    """Extract listing data from HTML using BeautifulSoup"""
    listings = []
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Find all listing sections - look for specific markers
        # The page has listings in specific containers
        listing_sections = soup.find_all('section')

        for section in listing_sections:
            # Check if this section contains a listing (has a detail link)
            detail_link = section.find('a', href=lambda x: x and '/bkdetail/' in x)
            if not detail_link:
                continue

            detail_url = detail_link.get('href', '')
            if not detail_url.startswith('http'):
                detail_url = urljoin(BASE_URL, detail_url)

            # Extract the detail ID from URL
            detail_id = detail_url.split('/bkdetail/')[-1].rstrip('/')

            # Extract text content
            text = section.get_text()

            # Extract building name from heading or first meaningful line
            heading = section.find(['h2', 'h3', 'h4'])
            building = heading.get_text(strip=True) if heading else ''

            # If no heading found, extract from first non-trivial line
            if not building:
                lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 2]
                for line in lines:
                    if not any(x in line for x in ['NEW', 'Used', 'View', 'Details', 'Open', 'Reno']):
                        building = line
                        break

            # Parse price (万円 format)
            price_raw = ''
            import re
            # Look for patterns like "15,490万円" or "152 million yen"
            price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*万|(\d+)\s*million', text)
            if price_match:
                if price_match.group(1):  # Japanese format
                    price_raw = price_match.group(1).replace(',', '')
                else:  # Million format
                    price_raw = str(int(price_match.group(2)) * 100)

            # Parse room type
            room_match = re.search(r'(\d+S?LDK|Studio)', text)
            room = room_match.group(1) if room_match else ''

            # Parse size (m²)
            size_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎡|m²)', text)
            size = size_match.group(1) if size_match else ''

            # Parse year
            year_match = re.search(r'(19[8-9]\d|20[0-2]\d)\s*年|Built\s+\w+\s+(19[8-9]\d|20[0-2]\d)', text)
            year = year_match.group(1) if year_match else ''

            # Parse floor (X/Y or just X)
            floor_match = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:floor|階)|(\d+)\s*(?:st|nd|rd|th)?\s*floor', text)
            floor = ''
            total_floors = ''
            if floor_match:
                if floor_match.group(3):  # Simple floor number
                    floor = floor_match.group(3)
                else:  # X/Y format
                    floor = floor_match.group(1)
                    total_floors = floor_match.group(2)

            # Parse walk time (minutes)
            walk_match = re.search(r'(\d+)\s*(?:[-–]?minute|分)', text, re.IGNORECASE)
            walk = walk_match.group(1) if walk_match else ''

            # Parse station name
            station = ''
            station_match = re.search(r'from\s+([^/\n]+?)\s+(?:Station|on the)|([^/\n]+?)駅', text)
            if station_match:
                station = station_match.group(1) or station_match.group(2)

            if building:  # Only add if we found a building name
                listings.append({
                    'building': building.strip(),
                    'price': price_raw,
                    'size': size,
                    'room': room,
                    'year': year,
                    'floor': floor,
                    'total_floors': total_floors,
                    'walk': walk,
                    'station': station.strip() if station else '',
                    'detail_url': detail_url,
                    'detail_id': detail_id
                })

        return listings
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []

def fetch_detail_page(detail_url: str) -> Optional[str]:
    """Fetch detail page HTML"""
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        return None
    except:
        return None

def extract_detail_info(html: str) -> Dict:
    """Extract ownership, fees, direction from detail page"""
    info = {
        'ownership': '',  # 所有権 (freehold) vs 借地権 (leasehold)
        'fees': 0,  # 管理費 + 修繕積立金
        'direction': '',  # 南/北/東/西 etc
        'can_rebuild': None  # 再建築可能
    }

    try:
        import re
        text = html

        # Check for ownership type (所有権 = freehold, 借地権 = leasehold)
        if '所有権' in text:
            info['ownership'] = '所有権'
        elif '借地権' in text:
            info['ownership'] = '借地権'

        # Check if can rebuild
        if '再建築可' in text:
            info['can_rebuild'] = True
        elif '再建築不可' in text:
            info['can_rebuild'] = False

        # Extract fees (usually found as 管理費:X万 修繕積立金:Y万 or combined)
        # Or look for pattern like "合計:X,XXX円/月"
        fee_match = re.search(r'(?:合計|管理費\+修繕):?\s*[¥円]*\s*(\d{1,5}(?:,\d{3})*)\s*(?:円|万)?/月', text)
        if fee_match:
            fee_str = fee_match.group(1).replace(',', '')
            info['fees'] = int(fee_str)

        # Extract direction (方角)
        for direction in ['南', '北', '東', '西', '南東', '南西', '北東', '北西']:
            if direction + '向' in text or f'向き{direction}' in text:
                info['direction'] = direction
                break

        return info
    except Exception as e:
        print(f"Error extracting detail info: {e}")
        return info

def should_pass_filters(listing: Dict, detail_info: Dict) -> Tuple[bool, str]:
    """Check if listing passes all hard filters"""

    # Parse year to int
    try:
        year = int(listing['year']) if listing['year'] else 0
    except:
        year = 0

    # Parse size to float
    try:
        size = float(listing['size']) if listing['size'] else 0
    except:
        size = 0

    # Parse walk time to int
    try:
        walk = int(listing['walk']) if listing['walk'] else 0
    except:
        walk = 0

    # Parse floor to int
    try:
        floor = int(listing['floor']) if listing['floor'] else 0
    except:
        floor = 0

    # Parse price to int (万円)
    try:
        price = int(listing['price']) if listing['price'] else 0
    except:
        price = 0

    # Hard filters from CLAUDE.md

    # 1. Built before 1982
    if year > 0 and year < 1982:
        return False, f"Built before 1982 ({year})"

    # 2. Smaller than 30m²
    if size > 0 and size < 30:
        return False, f"Smaller than 30m² ({size}m²)"

    # 3. Less than 1LDK
    if listing['room'] and not any(x in listing['room'] for x in ['LDK', 'DK']):
        return False, f"Less than 1LDK ({listing['room']})"

    # 4. Ground floor (1F)
    if floor == 1:
        return False, "Ground floor (1F)"

    # 5. More than 15 minutes walk to station
    if walk > 0 and walk > 15:
        return False, f"More than 15min walk ({walk}min)"

    # 6. North-only facing (北向き)
    if detail_info['direction'] == '北':
        return False, "North-only facing (北向き)"

    # 7. Monthly fees > ¥30,000
    if detail_info['fees'] > 30000:
        return False, f"Monthly fees > 30k (¥{detail_info['fees']:,})"

    # 8. Leasehold (借地権)
    if detail_info['ownership'] == '借地権':
        return False, "Leasehold (借地権)"

    # 9. Cannot be rebuilt (再建築不可)
    if detail_info['can_rebuild'] == False:
        return False, "Cannot be rebuilt (再建築不可)"

    return True, ""

def scrape_all_listings():
    """Main scraping function"""
    all_listings = []

    print("Starting Rehouse Koto-ku scraper...")
    print("Total expected: 246 listings across 9 pages")
    print()

    # Scrape all pages
    for page_num in range(1, 10):
        print(f"Scraping page {page_num}...")
        html = fetch_page(page_num)
        if not html:
            print(f"Failed to fetch page {page_num}, stopping")
            break

        listings = parse_listings_from_html(html)
        print(f"  Found {len(listings)} listings on page {page_num}")
        all_listings.extend(listings)

        time.sleep(1)  # Be respectful with requests

    print(f"\nTotal listings found: {len(all_listings)}")

    # Process each listing with filtering
    passed = []
    failed = []

    for idx, listing in enumerate(all_listings):
        print(f"\nProcessing listing {idx+1}/{len(all_listings)}: {listing['building']}")

        # Fetch detail page for additional info
        detail_html = fetch_detail_page(listing['detail_url'])
        detail_info = extract_detail_info(detail_html) if detail_html else {}

        # Check filters
        passes, reason = should_pass_filters(listing, detail_info)

        # Create output record
        if passes:
            record = f"PASS|{listing['building']}|{listing['price']}万|{listing['size']}|{listing['floor']}/{listing['total_floors']}|{listing['year']}|{listing['walk']}|{listing['station']}|¥{detail_info.get('fees', 0)}/mo|{listing['room']}|{detail_info.get('direction', 'N/A')}|{listing['detail_url']}"
            passed.append(record)
            print(f"  ✓ PASS")
        else:
            record = f"FAIL|{listing['building']}|{reason}|{listing['price']}万|{listing['size']}|{listing['year']}|{listing['station']}|{listing['detail_url']}"
            failed.append(record)
            print(f"  ✗ FAIL: {reason}")

        time.sleep(0.5)  # Rate limiting

    return passed, failed

if __name__ == '__main__':
    passed, failed = scrape_all_listings()

    print("\n" + "="*80)
    print(f"RESULTS: {len(passed)} PASS, {len(failed)} FAIL")
    print("="*80)

    print("\nPASSED LISTINGS:")
    print("-"*80)
    for record in passed:
        print(record)

    print(f"\n\nFAILED LISTINGS ({len(failed)} total):")
    print("-"*80)
    for record in failed[:20]:  # Show first 20 failures
        print(record)

    if len(failed) > 20:
        print(f"... and {len(failed) - 20} more failures")
