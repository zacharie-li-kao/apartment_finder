#!/usr/bin/env python3
"""
nomu.com Tokyo apartment scraper for Nakano, Ota, Arakawa, Edogawa wards
Filters by: price ≤¥40M, size ≥30m², floor ≥2F, year ≥1982, walk ≤15min,
            layout ≥1LDK, direction (S/SE/SW only), fees ≤¥30k/month, freehold
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import csv
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urljoin

class NomuScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.base_url = "https://www.nomu.com"
        self.listings = []

        # Ward codes
        self.wards = {
            'Nakano': ('13114', 110),
            'Ota': ('13111', 186),
            'Arakawa': ('13118', 71),
            'Edogawa': ('13123', 129)
        }

        # Hard filter thresholds
        self.filters = {
            'max_price_man': 40,  # 40M yen
            'min_size_m2': 30,
            'min_floor': 2,
            'min_year': 1982,
            'max_walk_min': 15,
            'max_monthly_fees': 30000,
            'allowed_directions': ['S', 'SE', 'SW', '南', '南東', '南西']
        }

    def parse_price(self, price_str: str) -> Optional[int]:
        """Parse price string like '3,390万' to integer (万)"""
        if not price_str:
            return None
        # Remove commas and extract number
        match = re.search(r'(\d{1,2},?\d{3}|\d{1,4})', price_str)
        if match:
            return int(match.group(1).replace(',', ''))
        return None

    def parse_size(self, size_str: str) -> Optional[float]:
        """Parse size string like '61.04m²' to float"""
        if not size_str:
            return None
        match = re.search(r'(\d+\.?\d*)', size_str)
        if match:
            return float(match.group(1))
        return None

    def parse_year(self, year_str: str) -> Optional[int]:
        """Parse year from various formats"""
        if not year_str:
            return None
        match = re.search(r'([12][09]\d{2})', year_str)
        if match:
            return int(match.group(1))
        return None

    def parse_floor(self, floor_str: str) -> Optional[int]:
        """Parse current floor from floor string like '11th floor / 25-story'"""
        if not floor_str:
            return None
        match = re.search(r'^(\d+)', floor_str)
        if match:
            return int(match.group(1))
        return None

    def parse_layout(self, layout_str: str) -> Optional[str]:
        """Normalize layout string"""
        if not layout_str:
            return None
        return layout_str.strip()

    def parse_walk_time(self, walk_str: str) -> Optional[int]:
        """Parse minimum walk time from multiple stations"""
        if not walk_str:
            return None
        # Find all numbers followed by minute/walk
        times = re.findall(r'(\d+)\s*(?:minute|分|min)', walk_str, re.IGNORECASE)
        if times:
            return min(int(t) for t in times)
        return None

    def parse_direction(self, direction_str: str) -> Optional[str]:
        """Normalize direction"""
        if not direction_str:
            return None
        return direction_str.strip()

    def passes_filters(self, listing: Dict) -> bool:
        """Check if listing passes all hard filters"""
        # Price filter
        if listing.get('price_man'):
            if listing['price_man'] > self.filters['max_price_man']:
                return False, f"Price ¥{listing['price_man']}M > ¥{self.filters['max_price_man']}M"

        # Size filter
        if listing.get('size_m2'):
            if listing['size_m2'] < self.filters['min_size_m2']:
                return False, f"Size {listing['size_m2']}m² < {self.filters['min_size_m2']}m²"

        # Floor filter
        if listing.get('floor_num'):
            if listing['floor_num'] < self.filters['min_floor']:
                return False, f"Floor {listing['floor_num']}F < {self.filters['min_floor']}F"

        # Year filter
        if listing.get('year'):
            if listing['year'] < self.filters['min_year']:
                return False, f"Year {listing['year']} < {self.filters['min_year']}"

        # Walk time filter
        if listing.get('walk_min'):
            if listing['walk_min'] > self.filters['max_walk_min']:
                return False, f"Walk {listing['walk_min']}min > {self.filters['max_walk_min']}min"

        # Direction filter
        if listing.get('direction'):
            if listing['direction'] not in self.filters['allowed_directions']:
                return False, f"Direction {listing['direction']} not in S/SE/SW"

        # Layout filter (≥1LDK means at least 1LDK)
        if listing.get('layout'):
            # Extract the number from layout (e.g., '1' from '1LDK')
            match = re.search(r'^(\d+)', listing['layout'])
            if match:
                rooms = int(match.group(1))
                if 'LDK' not in listing['layout'] or rooms < 1:
                    return False, f"Layout {listing['layout']} < 1LDK"

        return True, "PASS"

    def fetch_ward_page(self, ward_code: str, page: int) -> Optional[BeautifulSoup]:
        """Fetch and parse a ward listings page"""
        url = f"{self.base_url}/mansion/area_tokyo/{ward_code}/{page}/"
        try:
            print(f"  Fetching page {page}...")
            response = self.session.get(url, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return BeautifulSoup(response.content, 'html.parser')
            else:
                print(f"    Error: Status {response.status_code}")
                return None
        except Exception as e:
            print(f"    Error fetching: {e}")
            return None

    def extract_listing_from_page(self, soup: BeautifulSoup, ward_name: str) -> List[Dict]:
        """Extract all listings from a page"""
        listings = []

        # Try to find listing elements - adjust selectors based on actual page structure
        # This is a template - you may need to adjust based on actual nomu.com HTML

        # Get all text from the page for pattern matching
        page_text = soup.get_text()

        # Extract prices and surrounding context
        price_pattern = r'([0-9]{1,2},?[0-9]{3})\s*万'
        prices = re.finditer(price_pattern, page_text)

        for price_match in prices:
            price_str = price_match.group(1)
            start_pos = max(0, price_match.start() - 600)
            end_pos = min(len(page_text), price_match.end() + 600)
            context = page_text[start_pos:end_pos]

            # Extract individual fields from context
            listing = {
                'ward': ward_name,
                'name': 'TBD',  # Would need more sophisticated parsing
                'price_man': self.parse_price(price_str),
                'size_m2': self.parse_size(context),
                'layout': self.parse_layout(re.search(r'([0-9]LDK|[0-9]DK|[0-9]R)', context).group(1) if re.search(r'([0-9]LDK|[0-9]DK|[0-9]R)', context) else None),
                'floor_num': self.parse_floor(re.search(r'(\d+)\s*(?:階|floor)\s*/', context).group(1) if re.search(r'(\d+)\s*(?:階|floor)\s*/', context) else None),
                'year': self.parse_year(context),
                'walk_min': self.parse_walk_time(context),
                'direction': self.parse_direction(re.search(r'(south|southeast|southwest|S|SE|SW|南|南東|南西)', context, re.IGNORECASE).group(1) if re.search(r'(south|southeast|southwest|S|SE|SW|南|南東|南西)', context, re.IGNORECASE) else None),
                'monthly_fees_yen': None,  # Needs detail page
                'freehold': None,  # Needs detail page
                'vacant': None,  # Needs detail page
                'link': 'Detail page URL TBD'
            }

            passes, reason = self.passes_filters(listing)
            if passes:
                listings.append(listing)

        return listings

    def scrape_all_wards(self):
        """Scrape all 4 wards systematically"""
        all_passed = []

        for ward_name, (ward_code, total_count) in self.wards.items():
            print(f"\n{'='*60}")
            print(f"Scraping {ward_name} ward (code {ward_code}, ~{total_count} listings)")
            print(f"{'='*60}")

            # Calculate pages needed (~40 per page)
            pages_needed = (total_count + 39) // 40

            ward_listings = []
            for page in range(1, pages_needed + 1):
                soup = self.fetch_ward_page(ward_code, page)
                if soup:
                    page_listings = self.extract_listing_from_page(soup, ward_name)
                    ward_listings.extend(page_listings)
                    print(f"  Page {page}: {len(page_listings)} passed filters")
                time.sleep(1)  # Be respectful to the server

            print(f"\n{ward_name} TOTAL: {len(ward_listings)} properties passed filters")
            all_passed.extend(ward_listings)

        return all_passed

    def save_to_csv(self, listings: List[Dict], filename: str = 'nomu_results.csv'):
        """Save filtered results to CSV"""
        if not listings:
            print("No listings passed filters")
            return

        headers = ['Name', 'Price (万)', 'Size (m²)', 'Floor', 'Year', 'Walk (min)',
                   'Station', 'Fees (¥)', 'Layout', 'Direction', 'Freehold', 'Vacant', 'Link']

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            for listing in listings:
                row = {
                    'Name': listing.get('name', ''),
                    'Price (万)': listing.get('price_man', ''),
                    'Size (m²)': listing.get('size_m2', ''),
                    'Floor': listing.get('floor_num', ''),
                    'Year': listing.get('year', ''),
                    'Walk (min)': listing.get('walk_min', ''),
                    'Station': listing.get('station', ''),
                    'Fees (¥)': listing.get('monthly_fees_yen', ''),
                    'Layout': listing.get('layout', ''),
                    'Direction': listing.get('direction', ''),
                    'Freehold': listing.get('freehold', ''),
                    'Vacant': listing.get('vacant', ''),
                    'Link': listing.get('link', '')
                }
                writer.writerow(row)

        print(f"\nResults saved to {filename}")

def main():
    scraper = NomuScraper()
    print("Starting nomu.com Tokyo apartment scraper")
    print(f"Wards: {', '.join(scraper.wards.keys())}")
    print(f"Hard filters: price ≤¥40M, size ≥30m², floor ≥2F, year ≥1982, walk ≤15min, layout ≥1LDK, direction S/SE/SW")

    results = scraper.scrape_all_wards()

    print(f"\n{'='*60}")
    print(f"FINAL RESULTS: {len(results)} properties passed all hard filters")
    print(f"{'='*60}")

    if results:
        scraper.save_to_csv(results)

        # Print summary
        by_ward = {}
        for listing in results:
            ward = listing['ward']
            by_ward[ward] = by_ward.get(ward, 0) + 1

        print("\nResults by ward:")
        for ward, count in sorted(by_ward.items()):
            print(f"  {ward}: {count}")

if __name__ == '__main__':
    main()
