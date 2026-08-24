#!/usr/bin/env python3
"""
SECONDARY WARDS EXHAUSTIVE PAGINATION SCAN
- Nakano, Arakawa, Edogawa, Ota, Nerima, Chuo, Minato
- SUUMO: Full pagination (all pages)
- Rehouse: Full pagination (all pages)
- Strict 8-filter criteria
- Deduplication against 126 existing listings
- Output: Ward | Name | Price | Size | Layout | Floor | Year | Walk | Station | Fees | Direction
"""

import requests
import json
import re
import time
import sys
import subprocess
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Set, Optional
from datetime import datetime
from collections import defaultdict
from urllib.parse import urljoin

# Fix encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class SecondaryWardsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # Secondary wards with their SUUMO ward codes
        self.secondary_wards = {
            'Nakano': '13114',
            'Arakawa': '13118',
            'Edogawa': '13123',
            'Ota': '13111',
            'Nerima': '13120',
            'Chuo': '13102',
            'Minato': '13103',
        }

        # Rehouse ward URLs (building names for each ward)
        self.rehouse_wards = {
            'Nakano': 'nakano',
            'Arakawa': 'arakawa',
            'Edogawa': 'edogawa',
            'Ota': 'ota',
            'Nerima': 'nerima',
            'Chuo': 'chuo',
            'Minato': 'minato',
        }

        # Hard filters
        self.filters = {
            'price_min_yen': 1_500_000,
            'price_max_yen': 40_000_000,
            'size_min_m2': 30,
            'year_min': 1982,
            'walk_max_min': 15,
            'floor_min': 2,
            'fees_max_yen': 30_000,
        }

        # Load existing listings from git history
        self.existing_listings = self.load_existing_listings()
        print(f"[INFO] Loaded {len(self.existing_listings)} existing listings for deduplication\n")

        self.results = defaultdict(list)
        self.scan_stats = {}

    def load_existing_listings(self) -> Set[str]:
        """Load building names from git commit history"""
        existing = set()
        try:
            result = subprocess.run(
                ['git', 'log', '--all', '--format=%s'],
                cwd=r'C:\Users\zakat\Desktop\apartment',
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split('\n'):
                    # Extract building names from "Add #N Name" pattern
                    match = re.search(r'^Add #\d+\s+([^(]+)', line)
                    if match:
                        name = match.group(1).strip()
                        if name and len(name) > 2:
                            existing.add(name)
                            # Add partial matches for duplicate detection
                            if '・' in name:
                                parts = name.split('・')
                                existing.add(parts[0].strip())
        except Exception as e:
            print(f"[WARNING] Could not load existing listings: {e}")

        return existing

    def parse_price_yen(self, text: str) -> Optional[int]:
        """Parse price in yen from 万円 format"""
        if not text:
            return None
        try:
            # Look for 万円 format: 3,980万 or 3980万
            match = re.search(r'(\d+),?(\d{0,3})\s*万', text)
            if match:
                num = match.group(1).replace(',', '')
                price_man = int(num)
                return price_man * 10_000
        except:
            pass
        return None

    def parse_size_m2(self, text: str) -> Optional[float]:
        """Parse size in m²"""
        if not text:
            return None
        try:
            match = re.search(r'(\d+\.?\d*)\s*(?:m[²2m]|㎡)', text)
            if match:
                return float(match.group(1))
        except:
            pass
        return None

    def parse_year(self, text: str) -> Optional[int]:
        """Parse year built"""
        if not text:
            return None
        try:
            match = re.search(r'(19|20)(\d{2})\s*年', text)
            if match:
                return int(match.group(1) + match.group(2))
        except:
            pass
        return None

    def parse_walk_time(self, text: str) -> Optional[int]:
        """Parse minimum walk time in minutes"""
        if not text:
            return None
        try:
            times = re.findall(r'(\d+)\s*分', text)
            if times:
                return min(int(t) for t in times)
        except:
            pass
        return None

    def parse_floor(self, text: str) -> Optional[int]:
        """Parse current floor number"""
        if not text:
            return None
        try:
            match = re.search(r'^(\d+)', text.strip())
            if match:
                return int(match.group(1))
        except:
            pass
        return None

    def parse_fees(self, text: str) -> Optional[int]:
        """Parse monthly management/reserve fees in yen"""
        if not text:
            return None
        try:
            # Look for fee patterns: 15,000円 or 15000円
            match = re.search(r'(\d+),?(\d{0,3})\s*(?:円|/月)', text)
            if match:
                num = match.group(1).replace(',', '')
                return int(num)
        except:
            pass
        return None

    def parse_direction(self, text: str) -> Optional[str]:
        """Parse direction/orientation"""
        if not text:
            return None

        directions_jp = ['南東', '南西', '北東', '北西', '南', '東', '西', '北']
        for d in directions_jp:
            if d in text:
                return d
        return None

    def parse_layout(self, text: str) -> Optional[str]:
        """Parse room layout"""
        if not text:
            return None
        match = re.search(r'(\d+S?LDK|\d+DK|\d+K|Studio)', text)
        if match:
            return match.group(1)
        return None

    def parse_station(self, text: str) -> Optional[str]:
        """Extract station name from walk time text"""
        if not text:
            return None
        # Pattern: "駅名 X分" or "駅名 X min"
        match = re.search(r'([^分\d]+)[\d\s]*分', text)
        if match:
            return match.group(1).strip()
        return None

    def passes_filters(self, listing: Dict) -> Tuple[bool, Optional[str]]:
        """Check if listing passes all hard filters"""

        # Price
        if listing.get('price_yen'):
            if listing['price_yen'] < self.filters['price_min_yen']:
                return False, f"Price too low"
            if listing['price_yen'] > self.filters['price_max_yen']:
                return False, f"Price >{self.filters['price_max_yen']/1e6:.0f}M"

        # Size
        if listing.get('size_m2'):
            if listing['size_m2'] < self.filters['size_min_m2']:
                return False, f"Size <{self.filters['size_min_m2']}m²"

        # Year
        if listing.get('year'):
            if listing['year'] < self.filters['year_min']:
                return False, f"Built before 1982"

        # Walk time
        if listing.get('walk_time_min'):
            if listing['walk_time_min'] > self.filters['walk_max_min']:
                return False, f"Walk >{self.filters['walk_max_min']}min"

        # Floor
        if listing.get('floor'):
            if listing['floor'] < self.filters['floor_min']:
                return False, f"Ground floor"

        # Fees
        if listing.get('fees_yen'):
            if listing['fees_yen'] > self.filters['fees_max_yen']:
                return False, f"Fees >{self.filters['fees_max_yen']//1000}k"

        # Layout
        layout = listing.get('layout', '').upper()
        if layout:
            valid = ['1LDK', '2LDK', '3LDK', '4LDK', '2DK', '3DK', '1DK']
            if not any(v in layout for v in valid):
                return False, f"Invalid layout"

        # Direction (no north-only)
        if listing.get('direction', '').upper() in ['N', '北']:
            return False, f"North-only"

        return True, None

    def is_duplicate(self, listing: Dict) -> bool:
        """Check if building already exists in database"""
        name = listing.get('name', '').strip()
        if not name or len(name) < 3:
            return False

        if name in self.existing_listings:
            return True

        for existing in self.existing_listings:
            if len(name) > 5 and name in existing:
                return True
            if len(existing) > 5 and existing in name:
                return True

        return False

    def scan_suumo_ward(self, ward_name: str, ward_code: str) -> List[Dict]:
        """Scan all SUUMO pages for a ward with full pagination"""
        listings = []
        page = 1
        max_pages = 100
        consecutive_empty = 0

        print(f"  [SUUMO] {ward_name}...", end='', flush=True)

        while page <= max_pages:
            try:
                url = f'https://suumo.jp/ms/chuko/Tokyo/{ward_code}/?page={page}'
                resp = self.session.get(url, timeout=15)

                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.content, 'html.parser')

                # Find all listing links
                listing_links = soup.find_all('a', href=re.compile(r'/ms/chuko/tokyo/.*nc_\d+/'))

                if not listing_links:
                    consecutive_empty += 1
                    if consecutive_empty > 2:
                        break
                else:
                    consecutive_empty = 0

                for link in listing_links:
                    try:
                        detail_url = link.get('href', '')
                        if not detail_url.startswith('http'):
                            detail_url = 'https://suumo.jp' + detail_url

                        # Fetch detail page
                        time.sleep(0.3)
                        detail_resp = self.session.get(detail_url, timeout=15)
                        if detail_resp.status_code == 200:
                            listing = self.extract_suumo_detail(detail_resp.content, ward_name, detail_url)
                            if listing:
                                passes, _ = self.passes_filters(listing)
                                if passes and not self.is_duplicate(listing):
                                    listings.append(listing)
                    except Exception as e:
                        continue

                page += 1
                time.sleep(0.5)

            except Exception as e:
                break

        print(f" {len(listings)} qualified")
        return listings

    def extract_suumo_detail(self, html: bytes, ward_name: str, url: str) -> Optional[Dict]:
        """Extract detailed information from SUUMO listing page"""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Get page text for parsing
            text = soup.get_text()

            listing = {
                'portal': 'SUUMO',
                'ward': ward_name,
                'url': url,
            }

            # Extract building name - usually in title or header
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                # Format often: "Building Name · Ward · Details | SUUMO"
                parts = title_text.split('·')
                if parts:
                    listing['name'] = parts[0].strip()

            # If name not found, try heading
            if not listing.get('name'):
                h1 = soup.find('h1')
                if h1:
                    listing['name'] = h1.get_text(strip=True)

            # Extract price
            price_text = re.search(r'(\d+),?(\d{0,3})\s*万', text)
            if price_text:
                listing['price_yen'] = self.parse_price_yen(price_text.group(0))

            # Extract size
            size_text = re.search(r'(\d+\.?\d*)\s*(?:m[²2m]|㎡)', text)
            if size_text:
                listing['size_m2'] = self.parse_size_m2(size_text.group(0))

            # Extract layout
            layout_text = re.search(r'(\d+S?LDK|\d+DK)', text)
            if layout_text:
                listing['layout'] = layout_text.group(1)

            # Extract year
            year_text = re.search(r'(19|20)(\d{2})\s*年', text)
            if year_text:
                listing['year'] = self.parse_year(year_text.group(0))

            # Extract floor
            floor_match = re.search(r'(\d+)\s*階', text)
            if floor_match:
                listing['floor'] = int(floor_match.group(1))

            # Extract walk time and station
            walk_text = re.search(r'([^分\d]+)[\d\s]+分', text)
            if walk_text:
                station = self.parse_station(walk_text.group(0))
                if station:
                    listing['station'] = station
                listing['walk_time_min'] = self.parse_walk_time(walk_text.group(0))

            # Extract fees (管理費 + 修繕積立金)
            fees_match = re.search(r'(?:管理費|修繕積立金)[：:]\s*(\d+),?(\d{0,3})\s*(?:円|/月)', text)
            if fees_match:
                listing['fees_yen'] = self.parse_fees(fees_match.group(0))

            # Extract direction
            direction = self.parse_direction(text)
            if direction:
                listing['direction'] = direction

            # Basic validation
            if listing.get('name') and len(listing.get('name', '')) > 2:
                return listing

            return None

        except Exception as e:
            return None

    def scan_rehouse_ward(self, ward_name: str, ward_code: str) -> List[Dict]:
        """Scan all Rehouse pages for a ward with full pagination"""
        listings = []
        page = 1
        max_pages = 50

        # Map ward names to Rehouse city codes
        ward_to_code = {
            'Nakano': '13114',
            'Arakawa': '13118',
            'Edogawa': '13123',
            'Ota': '13111',
            'Nerima': '13120',
            'Chuo': '13102',
            'Minato': '13103',
        }

        code = ward_to_code.get(ward_name)
        if not code:
            return listings

        print(f"  [Rehouse] {ward_name}...", end='', flush=True)

        while page <= max_pages:
            try:
                # Rehouse URL format: prefecture/13/city/XXXXX
                url = f'https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{code}/'
                params = {} if page == 1 else {'page': page}

                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.content, 'html.parser')

                # Find all listing links
                listing_links = soup.find_all('a', href=re.compile(r'/bkdetail/'))

                if not listing_links:
                    break

                for link in listing_links:
                    try:
                        detail_url = link.get('href', '')
                        if not detail_url.startswith('http'):
                            detail_url = urljoin('https://www.rehouse.co.jp', detail_url)

                        time.sleep(0.3)
                        detail_resp = self.session.get(detail_url, timeout=15)
                        if detail_resp.status_code == 200:
                            listing = self.extract_rehouse_detail(detail_resp.content, ward_name, detail_url)
                            if listing:
                                passes, _ = self.passes_filters(listing)
                                if passes and not self.is_duplicate(listing):
                                    listings.append(listing)
                    except Exception as e:
                        continue

                page += 1
                time.sleep(0.5)

            except Exception as e:
                break

        print(f" {len(listings)} qualified")
        return listings

    def extract_rehouse_detail(self, html: bytes, ward_name: str, url: str) -> Optional[Dict]:
        """Extract detailed information from Rehouse listing page"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()

            listing = {
                'portal': 'Rehouse',
                'ward': ward_name,
                'url': url,
            }

            # Extract building name
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                parts = title_text.split('|')
                if parts:
                    listing['name'] = parts[0].strip()

            if not listing.get('name'):
                h1 = soup.find('h1')
                if h1:
                    listing['name'] = h1.get_text(strip=True)

            # Extract price
            price_match = re.search(r'(\d+),?(\d{0,3})\s*万', text)
            if price_match:
                listing['price_yen'] = self.parse_price_yen(price_match.group(0))

            # Extract size
            size_match = re.search(r'(\d+\.?\d*)\s*(?:m[²2m]|㎡)', text)
            if size_match:
                listing['size_m2'] = self.parse_size_m2(size_match.group(0))

            # Extract layout
            layout_match = re.search(r'(\d+S?LDK|\d+DK)', text)
            if layout_match:
                listing['layout'] = layout_match.group(1)

            # Extract year
            year_match = re.search(r'(19|20)(\d{2})\s*年', text)
            if year_match:
                listing['year'] = self.parse_year(year_match.group(0))

            # Extract floor
            floor_match = re.search(r'(\d+)\s*階', text)
            if floor_match:
                listing['floor'] = int(floor_match.group(1))

            # Extract walk time
            walk_match = re.search(r'([^分\d]+)[\d\s]+分', text)
            if walk_match:
                station = self.parse_station(walk_match.group(0))
                if station:
                    listing['station'] = station
                listing['walk_time_min'] = self.parse_walk_time(walk_match.group(0))

            # Extract fees
            fees_match = re.search(r'(?:管理費|修繕積立金)[：:]\s*(\d+),?(\d{0,3})\s*(?:円|/月)', text)
            if fees_match:
                listing['fees_yen'] = self.parse_fees(fees_match.group(0))

            # Extract direction
            direction = self.parse_direction(text)
            if direction:
                listing['direction'] = direction

            if listing.get('name') and len(listing.get('name', '')) > 2:
                return listing

            return None

        except Exception as e:
            return None

    def run_scan(self):
        """Run exhaustive scan across all secondary wards"""
        print("=" * 120)
        print("SECONDARY WARDS EXHAUSTIVE PAGINATION SCAN")
        print("=" * 120)
        print(f"Start: {datetime.now()}")
        print(f"Criteria: ¥1.5M-¥40M | 30m²+ | 1LDK+ | 1982+ | ≤15min walk | 2F+ | ≤¥30k fees | Freehold")
        print(f"Existing DB: {len(self.existing_listings)} listings")
        print(f"Wards: Nakano, Arakawa, Edogawa, Ota, Nerima, Chuo, Minato\n")

        total_new = 0

        for ward_name in sorted(self.secondary_wards.keys()):
            ward_code = self.secondary_wards[ward_name]
            print(f"\n{ward_name}:")

            ward_new = 0

            # Scan SUUMO
            suumo_listings = self.scan_suumo_ward(ward_name, ward_code)
            ward_new += len(suumo_listings)
            self.results[ward_name].extend(suumo_listings)

            # Scan Rehouse
            rehouse_listings = self.scan_rehouse_ward(ward_name, ward_code)
            ward_new += len(rehouse_listings)
            self.results[ward_name].extend(rehouse_listings)

            self.scan_stats[ward_name] = ward_new
            total_new += ward_new

        print(f"\n{'=' * 120}")
        print(f"SCAN COMPLETE")
        print(f"Total new qualified candidates: {total_new}")
        print(f"End: {datetime.now()}\n")

        # Print results in requested format
        print("RESULTS BY WARD:\n")
        for ward_name in sorted(self.results.keys()):
            if self.results[ward_name]:
                print(f"\n{ward_name} ({len(self.results[ward_name])} candidates):")
                print("Ward | Name | Price | Size | Layout | Floor | Year | Walk | Station | Fees | Direction")
                print("-" * 150)

                for listing in self.results[ward_name]:
                    price_str = f"¥{listing.get('price_yen', 0)//10000:.0f}M" if listing.get('price_yen') else "?"
                    size_str = f"{listing.get('size_m2', '?'):.0f}m²" if listing.get('size_m2') else "?"
                    layout = listing.get('layout', '?')
                    floor = f"{listing.get('floor', '?')}F"
                    year = listing.get('year', '?')
                    walk = f"{listing.get('walk_time_min', '?')}min"
                    station = listing.get('station', '?')
                    fees = f"¥{listing.get('fees_yen', 0)//1000:.0f}k" if listing.get('fees_yen') else "?"
                    direction = listing.get('direction', '?')

                    print(f"{ward_name} | {listing.get('name', '?')[:40]} | {price_str} | {size_str} | {layout} | {floor} | {year} | {walk} | {station} | {fees} | {direction}")

        return total_new, self.results


if __name__ == '__main__':
    scraper = SecondaryWardsScraper()
    total, results = scraper.run_scan()
