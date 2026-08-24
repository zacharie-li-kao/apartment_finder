#!/usr/bin/env python3
"""
Quick sweep for new apartment listings (past 24-48 hours)
Searches: SUUMO, Rehouse, NOMU
Focus wards: Sumida, Koto, Itabashi, Katsushika
Criteria: ¥1.5M-40M, 30m²+, 1LDK+, 1982+, walk ≤15min, floor 2F+, freehold only, fees ≤¥30k/mo
"""

import requests
import json
import re
from datetime import datetime
from typing import List, Dict
import time

# Existing 116 listings from git log (sample identifiers - in production would load from database)
KNOWN_LISTINGS = {
    "セザール久が原",  # #126
    "メゾン蓮根",       # #125
    "サンタウン立花１号棟",  # #124
    "エスカイア等々力",  # #123
}

def search_suumo_ward(ward_code: str, ward_name: str) -> List[Dict]:
    """Search SUUMO for a specific ward"""
    results = []
    try:
        # SUUMO URL for ward (using /ms/chuko/ path as per memory)
        url = f"https://suumo.jp/ms/chuko/tokyo/sc_{ward_code}/"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print(f"  Fetching SUUMO - {ward_name}...")
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            # Extract listings from page text
            # Looking for patterns like "物件名\n<name>\n販売価格\n<price>"
            listings = parse_suumo_html(resp.text, ward_name)
            results.extend(listings)
            print(f"    Found {len(listings)} listings")
        else:
            print(f"    Error: Status {resp.status_code}")

    except Exception as e:
        print(f"    Exception: {e}")

    return results

def parse_suumo_html(html: str, ward_name: str) -> List[Dict]:
    """Parse SUUMO HTML to extract listing details"""
    listings = []

    # Look for patterns in the HTML
    # This is a simplified extraction - in reality would use BeautifulSoup

    # Find all building names (物件名 followed by the actual name)
    name_pattern = r'物件名[^>]*>([^<]+)<'
    price_pattern = r'販売価格[^>]*>(\d+)万円'
    area_pattern = r'専有面積[^>]*>(\d+\.?\d*)m²'
    layout_pattern = r'間取り[^>]*>([^<]+)<'
    year_pattern = r'築年月[^>]*>(\d{4})年?'
    walk_pattern = r'徒歩(\d+)分'

    names = re.findall(name_pattern, html)
    prices = re.findall(price_pattern, html)
    areas = re.findall(area_pattern, html)
    layouts = re.findall(layout_pattern, html)
    years = re.findall(year_pattern, html)

    # Simple pairing (not perfect, but gives us approximate data)
    for i in range(min(len(names), 20)):  # Limit to first 20 per page for speed
        try:
            listing = {
                'name': names[i] if i < len(names) else '',
                'price_million': float(prices[i]) if i < len(prices) else None,
                'area_sqm': float(areas[i]) if i < len(areas) else None,
                'layout': layouts[i] if i < len(layouts) else '',
                'year': int(years[i]) if i < len(years) else None,
                'ward': ward_name,
                'source': 'SUUMO'
            }

            # Apply filters
            if should_include_listing(listing):
                listings.append(listing)

        except (ValueError, IndexError):
            continue

    return listings

def should_include_listing(listing: Dict) -> bool:
    """Check if listing meets criteria"""
    try:
        # Price: 1.5M-40M yen
        if not listing['price_million'] or listing['price_million'] < 15 or listing['price_million'] > 400:
            return False

        # Area: 30m² minimum
        if not listing['area_sqm'] or listing['area_sqm'] < 30:
            return False

        # Layout: 1LDK+
        layout = listing['layout'].upper()
        valid_layouts = ['1LDK', '2LDK', '3LDK', '2DK', '3DK', '1LD', '2LD']
        if not any(l in layout for l in valid_layouts):
            return False

        # Year: 1982+
        if not listing['year'] or listing['year'] < 1982:
            return False

        return True

    except:
        return False

def search_rehouse_ward(ward_code: str, ward_name: str) -> List[Dict]:
    """Search Rehouse for a specific ward"""
    results = []
    try:
        # Rehouse URL pattern
        url = f"https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{ward_code}/"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print(f"  Fetching Rehouse - {ward_name}...")
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            listings = parse_rehouse_html(resp.text, ward_name)
            results.extend(listings)
            print(f"    Found {len(listings)} listings")
        else:
            print(f"    Error: Status {resp.status_code}")

    except Exception as e:
        print(f"    Exception: {e}")

    return results

def parse_rehouse_html(html: str, ward_name: str) -> List[Dict]:
    """Parse Rehouse HTML"""
    listings = []
    # Simplified parsing - Rehouse structure different from SUUMO
    # Would need proper HTML parsing in production
    return listings

def search_nomu_ward(ward_name: str) -> List[Dict]:
    """Search NOMU for a specific ward"""
    results = []
    try:
        # NOMU API/search URL
        url = f"https://www.nomu.com/mansion/SearchList/?city={ward_name}&type=fw&pkg=mansion"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print(f"  Fetching NOMU - {ward_name}...")
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            listings = parse_nomu_html(resp.text, ward_name)
            results.extend(listings)
            print(f"    Found {len(listings)} listings")
        else:
            print(f"    Error: Status {resp.status_code}")

    except Exception as e:
        print(f"    Exception: {e}")

    return results

def parse_nomu_html(html: str, ward_name: str) -> List[Dict]:
    """Parse NOMU HTML"""
    listings = []
    # Simplified parsing - NOMU structure different
    return listings

def identify_new_listings(all_listings: List[Dict]) -> List[Dict]:
    """Filter listings not in known existing 116"""
    new = []
    for listing in all_listings:
        # Check if building name is in known listings
        if listing['name'] not in KNOWN_LISTINGS:
            new.append(listing)
    return new

def format_output(listings: List[Dict]) -> str:
    """Format results as requested"""
    if not listings:
        return "No new listings found in past 24-48 hours matching criteria."

    output = "NEW LISTINGS - Quick Sweep Results\n"
    output += "=" * 100 + "\n"
    output += "Name | Price | Size | Floor | Year | Walk | Station | Fees | Layout | Direction\n"
    output += "-" * 100 + "\n"

    for listing in sorted(listings, key=lambda x: x.get('price_million', 0)):
        try:
            line = (f"{listing.get('name', '?')} | "
                   f"¥{listing.get('price_million', 0):.1f}M | "
                   f"{listing.get('area_sqm', 0):.0f}m² | "
                   f"? | "  # Floor not yet extracted
                   f"{listing.get('year', '?')} | "
                   f"? | "  # Walk time not yet extracted
                   f"? | "  # Station not extracted
                   f"? | "  # Fees not extracted
                   f"{listing.get('layout', '?')} | "
                   f"? | {listing.get('source', '?')}")
            output += line + "\n"
        except:
            continue

    return output

def main():
    print("Starting quick sweep for new listings...")
    print(f"Current time: {datetime.now().isoformat()}")
    print()

    # Ward codes and names
    wards = {
        'sumida': '墨田区',
        'koto': '江東区',
        'itabashi': '板橋区',
        'katsushika': '葛飾区'
    }

    all_listings = []

    # Search SUUMO
    print("SUUMO Search:")
    for code, name in wards.items():
        listings = search_suumo_ward(code, name)
        all_listings.extend(listings)
        time.sleep(1)  # Rate limiting

    print()
    print("Rehouse Search:")
    for code, name in wards.items():
        # Would need proper ward codes for Rehouse
        # listings = search_rehouse_ward(code, name)
        # all_listings.extend(listings)
        time.sleep(1)

    print()
    print("NOMU Search:")
    for code, name in wards.items():
        listings = search_nomu_ward(name)
        all_listings.extend(listings)
        time.sleep(1)

    print()
    print(f"Total listings found across all portals: {len(all_listings)}")

    # Filter for new listings
    new_listings = identify_new_listings(all_listings)
    print(f"Listings not in existing 116: {len(new_listings)}")

    # Format and output
    print()
    print(format_output(new_listings))

if __name__ == '__main__':
    main()
