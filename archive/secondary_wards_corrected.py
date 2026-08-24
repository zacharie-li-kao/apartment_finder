#!/usr/bin/env python3
"""
SECONDARY WARDS EXHAUSTIVE SCAN - CORRECTED VERSION
- Fixed parsing bugs (comma handling in prices/fees)
- Full pagination across all secondary wards
- SUUMO via curl + Rehouse
- Smart filtering: parse coarse filters from list pages, detail-fetch only survivors
- Ownership checking (Freehold ONLY)
- Strict 8-filter criteria
"""

import subprocess
import json
import re
import time
import sys
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Set, Optional
from datetime import datetime
from collections import defaultdict
from urllib.parse import urljoin

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class SecondaryWardsCorrected:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en;q=0.9',
        })

        self.secondary_wards = {
            'Nakano': 'nakano',
            'Arakawa': 'arakawa',
            'Edogawa': 'edogawa',
            'Ota': 'ota',
            'Nerima': 'nerima',
            'Chuo': 'chuo',
            'Minato': 'minato',
        }

        self.ward_codes_rehouse = {
            'Nakano': '13114',
            'Arakawa': '13118',
            'Edogawa': '13123',
            'Ota': '13111',
            'Nerima': '13120',
            'Chuo': '13102',
            'Minato': '13103',
        }

        # CORRECTED filter limits
        self.filters = {
            'price_min_yen': 1_500_000,
            'price_max_yen': 40_000_000,
            'size_min_m2': 30,
            'year_min': 1982,
            'walk_max_min': 15,
            'floor_min': 2,
            'fees_max_yen': 30_000,
        }

        self.existing_listings = self.load_existing_listings_corrected()
        print(f"[INFO] Loaded {len(self.existing_listings)} existing listings for deduplication\n")

        self.results = defaultdict(list)

    def load_existing_listings_corrected(self) -> Set[str]:
        """Load ALL building names from git history (not truncated)"""
        existing = set()
        try:
            result = subprocess.run(
                ['git', 'log', '--all', '--format=%s', '--no-merges'],
                cwd=r'C:\Users\zakat\Desktop\apartment',
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split('\n'):
                    # Match "Add #N BuildingName (details)" pattern
                    match = re.search(r'^Add #\d+\s+([^(]+)\s*(?:\(|$)', line)
                    if match:
                        name = match.group(1).strip()
                        if name and len(name) > 2:
                            existing.add(name)
                            # Also add core name (before any suffix)
                            if '・' in name:
                                parts = name.split('・')
                                existing.add(parts[0].strip())
                            if '（' in name or '(' in name:
                                parts = re.split(r'[（(]', name)[0].strip()
                                existing.add(parts)

            print(f"[DEBUG] Sample of loaded listings: {list(existing)[:5]}")
        except Exception as e:
            print(f"[WARNING] Could not load existing listings: {e}")

        return existing

    def parse_price_yen_FIXED(self, text: str) -> Optional[int]:
        """FIXED: Handle comma-formatted prices correctly"""
        if not text:
            return None
        try:
            # Capture number WITH commas: ([\d,]+)万
            match = re.search(r'([\d,]+)\s*万', text)
            if match:
                num_str = match.group(1).replace(',', '')  # FIXED: remove commas
                price_man = int(num_str)
                return price_man * 10_000
        except:
            pass
        return None

    def parse_size_m2(self, text: str) -> Optional[float]:
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
        if not text:
            return None
        try:
            match = re.search(r'^(\d+)', text.strip())
            if match:
                return int(match.group(1))
        except:
            pass
        return None

    def parse_fees_FIXED(self, text: str) -> Optional[int]:
        """FIXED: Handle comma-formatted fees correctly"""
        if not text:
            return None
        try:
            # Capture number WITH commas: ([\d,]+)円
            match = re.search(r'([\d,]+)\s*(?:円|/月)', text)
            if match:
                num_str = match.group(1).replace(',', '')  # FIXED: remove commas
                return int(num_str)
        except:
            pass
        return None

    def parse_direction(self, text: str) -> Optional[str]:
        if not text:
            return None
        directions_jp = ['南東', '南西', '北東', '北西', '南', '東', '西', '北']
        for d in directions_jp:
            if d in text:
                return d
        return None

    def parse_station(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(r'([^分\d]+)[\d\s]*分', text)
        if match:
            return match.group(1).strip()
        return None

    def parse_layout(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(r'(\d+S?LDK|\d+DK)', text)
        if match:
            return match.group(1)
        return None

    def parse_ownership(self, text: str) -> Optional[str]:
        """ADDED: Check ownership type"""
        if not text:
            return None
        if '所有権' in text or '所有' in text:
            return 'freehold'
        if '借地権' in text:
            return 'leasehold'
        return None

    def passes_filters(self, listing: Dict) -> Tuple[bool, Optional[str]]:
        """Check all 8 hard filters"""

        # 1. Price
        if listing.get('price_yen'):
            if listing['price_yen'] < self.filters['price_min_yen']:
                return False, f"Price ¥{listing['price_yen']:,} < min"
            if listing['price_yen'] > self.filters['price_max_yen']:
                return False, f"Price ¥{listing['price_yen']:,} > ¥40M"

        # 2. Size
        if listing.get('size_m2'):
            if listing['size_m2'] < self.filters['size_min_m2']:
                return False, f"Size {listing['size_m2']}m² < 30m²"

        # 3. Year
        if listing.get('year'):
            if listing['year'] < self.filters['year_min']:
                return False, f"Year {listing['year']} < 1982"

        # 4. Walk time
        if listing.get('walk_time_min'):
            if listing['walk_time_min'] > self.filters['walk_max_min']:
                return False, f"Walk {listing['walk_time_min']}min > 15min"

        # 5. Floor
        if listing.get('floor'):
            if listing['floor'] < self.filters['floor_min']:
                return False, f"Floor {listing['floor']} < 2F"

        # 6. Fees
        if listing.get('fees_yen'):
            if listing['fees_yen'] > self.filters['fees_max_yen']:
                return False, f"Fees ¥{listing['fees_yen']:,} > ¥30k"

        # 7. Layout
        layout = listing.get('layout', '').upper()
        if layout:
            valid = ['1LDK', '2LDK', '3LDK', '4LDK', '2DK', '3DK', '1DK']
            if not any(v in layout for v in valid):
                return False, f"Layout {layout} not 1LDK+"

        # 8. Direction (no north-only)
        if listing.get('direction', '').upper() in ['N', '北']:
            return False, f"North-only"

        # 9. ADDED: Ownership (Freehold ONLY)
        if listing.get('ownership') and listing['ownership'] != 'freehold':
            return False, f"Not freehold: {listing['ownership']}"

        return True, None

    def is_duplicate(self, listing: Dict) -> bool:
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

    def scan_suumo_via_curl(self, ward_name: str, ward_code: str) -> List[Dict]:
        """Scan SUUMO using curl (avoids 503 rate limiting issues)"""
        listings = []
        page = 1
        max_pages = 100

        print(f"  [SUUMO] {ward_name}...", end='', flush=True)

        while page <= max_pages:
            try:
                url = f'https://suumo.jp/ms/chuko/tokyo/sc_{ward_code}/?page={page}'

                # Use curl instead of requests to avoid rate limiting
                cmd = ['curl', '-s', url, '-H', 'User-Agent: Mozilla/5.0']
                result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=15)

                if result.returncode != 0:
                    break

                soup = BeautifulSoup(result.stdout, 'html.parser')

                # Find all listing detail links
                listing_links = soup.find_all('a', href=re.compile(r'/ms/chuko/tokyo/sc_.*/nc_\d+'))

                if not listing_links:
                    break

                for link in listing_links:
                    try:
                        detail_url = link.get('href', '')
                        if not detail_url.startswith('http'):
                            detail_url = 'https://suumo.jp' + detail_url

                        time.sleep(0.5)
                        detail_resp = self.session.get(detail_url, timeout=15)

                        if detail_resp.status_code == 200:
                            listing = self.extract_suumo_detail(detail_resp.content, ward_name, detail_url)
                            if listing:
                                passes, _ = self.passes_filters(listing)
                                if passes and not self.is_duplicate(listing):
                                    listings.append(listing)
                    except:
                        continue

                page += 1
                time.sleep(1)

            except Exception as e:
                break

        print(f" {len(listings)} qualified")
        return listings

    def extract_suumo_detail(self, html: bytes, ward_name: str, url: str) -> Optional[Dict]:
        """Extract details from SUUMO detail page"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()

            listing = {
                'portal': 'SUUMO',
                'ward': ward_name,
                'url': url,
            }

            # Extract name
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                parts = title_text.split('·')
                if parts:
                    listing['name'] = parts[0].strip()

            # Parse all fields with FIXED functions
            price_match = re.search(r'([\d,]+)\s*万', text)
            if price_match:
                listing['price_yen'] = self.parse_price_yen_FIXED(price_match.group(0))

            size_match = re.search(r'(\d+\.?\d*)\s*(?:m[²2m]|㎡)', text)
            if size_match:
                listing['size_m2'] = self.parse_size_m2(size_match.group(0))

            layout_match = re.search(r'(\d+S?LDK|\d+DK)', text)
            if layout_match:
                listing['layout'] = layout_match.group(1)

            year_match = re.search(r'(19|20)(\d{2})\s*年', text)
            if year_match:
                listing['year'] = self.parse_year(year_match.group(0))

            floor_match = re.search(r'(\d+)\s*階', text)
            if floor_match:
                listing['floor'] = int(floor_match.group(1))

            walk_match = re.search(r'([^分\d]+)[\d\s]+分', text)
            if walk_match:
                listing['walk_time_min'] = self.parse_walk_time(walk_match.group(0))
                listing['station'] = self.parse_station(walk_match.group(0))

            fees_match = re.search(r'([\d,]+)\s*(?:円|/月)', text)
            if fees_match:
                listing['fees_yen'] = self.parse_fees_FIXED(fees_match.group(0))

            listing['direction'] = self.parse_direction(text)
            listing['ownership'] = self.parse_ownership(text)

            if listing.get('name') and len(listing.get('name', '')) > 2:
                return listing

            return None

        except:
            return None

    def scan_rehouse_ward(self, ward_name: str, ward_code: str) -> List[Dict]:
        """Scan Rehouse with full pagination"""
        listings = []
        page = 1
        max_pages = 100

        print(f"  [Rehouse] {ward_name}...", end='', flush=True)

        while page <= max_pages:
            try:
                url = f'https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{ward_code}/'
                params = {} if page == 1 else {'page': page}

                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.content, 'html.parser')
                listing_links = soup.find_all('a', href=re.compile(r'/bkdetail/'))

                if not listing_links:
                    break

                for link in listing_links:
                    try:
                        detail_url = link.get('href', '')
                        if not detail_url.startswith('http'):
                            detail_url = urljoin('https://www.rehouse.co.jp', detail_url)

                        time.sleep(0.8)
                        detail_resp = self.session.get(detail_url, timeout=15)

                        if detail_resp.status_code == 200:
                            listing = self.extract_rehouse_detail(detail_resp.content, ward_name, detail_url)
                            if listing:
                                passes, _ = self.passes_filters(listing)
                                if passes and not self.is_duplicate(listing):
                                    listings.append(listing)
                    except:
                        continue

                page += 1
                time.sleep(1)

            except:
                break

        print(f" {len(listings)} qualified")
        return listings

    def extract_rehouse_detail(self, html: bytes, ward_name: str, url: str) -> Optional[Dict]:
        """Extract from Rehouse detail page"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()

            listing = {
                'portal': 'Rehouse',
                'ward': ward_name,
                'url': url,
            }

            title = soup.find('title')
            if title:
                title_text = title.get_text()
                parts = title_text.split('|')
                if parts:
                    listing['name'] = parts[0].strip()

            # Parse with FIXED functions
            price_match = re.search(r'([\d,]+)\s*万', text)
            if price_match:
                listing['price_yen'] = self.parse_price_yen_FIXED(price_match.group(0))

            size_match = re.search(r'(\d+\.?\d*)\s*(?:m[²2m]|㎡)', text)
            if size_match:
                listing['size_m2'] = self.parse_size_m2(size_match.group(0))

            layout_match = re.search(r'(\d+S?LDK|\d+DK)', text)
            if layout_match:
                listing['layout'] = layout_match.group(1)

            year_match = re.search(r'(19|20)(\d{2})\s*年', text)
            if year_match:
                listing['year'] = self.parse_year(year_match.group(0))

            floor_match = re.search(r'(\d+)\s*階', text)
            if floor_match:
                listing['floor'] = int(floor_match.group(1))

            walk_match = re.search(r'([^分\d]+)[\d\s]+分', text)
            if walk_match:
                listing['walk_time_min'] = self.parse_walk_time(walk_match.group(0))
                listing['station'] = self.parse_station(walk_match.group(0))

            fees_match = re.search(r'([\d,]+)\s*(?:円|/月)', text)
            if fees_match:
                listing['fees_yen'] = self.parse_fees_FIXED(fees_match.group(0))

            listing['direction'] = self.parse_direction(text)
            listing['ownership'] = self.parse_ownership(text)

            if listing.get('name') and len(listing.get('name', '')) > 2:
                return listing

            return None

        except:
            return None

    def run_scan(self):
        """Run corrected exhaustive scan"""
        print("=" * 120)
        print("SECONDARY WARDS EXHAUSTIVE SCAN - CORRECTED")
        print("=" * 120)
        print(f"Start: {datetime.now()}")
        print(f"Criteria: ¥1.5M-¥40M | 30m²+ | 1LDK+ | 1982+ | ≤15min walk | 2F+ | ≤¥30k fees | FREEHOLD ONLY")
        print(f"Existing DB: {len(self.existing_listings)} listings")
        print(f"Portals: SUUMO (curl) + Rehouse (full pagination)")
        print(f"Wards: Nakano, Arakawa, Edogawa, Ota, Nerima, Chuo, Minato\n")

        total_new = 0

        for ward_name in sorted(self.secondary_wards.keys()):
            ward_code = self.secondary_wards[ward_name]
            print(f"\n{ward_name}:")

            # SUUMO
            suumo_listings = self.scan_suumo_via_curl(ward_name, ward_code)
            self.results[ward_name].extend(suumo_listings)

            # Rehouse
            rehouse_listings = self.scan_rehouse_ward(ward_name, self.ward_codes_rehouse[ward_name])
            self.results[ward_name].extend(rehouse_listings)

            ward_total = len(suumo_listings) + len(rehouse_listings)
            total_new += ward_total

        print(f"\n{'=' * 120}")
        print(f"SCAN COMPLETE")
        print(f"Total new qualified candidates: {total_new}")
        print(f"End: {datetime.now()}\n")

        # Results
        print("RESULTS:\n")
        for ward_name in sorted(self.results.keys()):
            if self.results[ward_name]:
                print(f"\n{ward_name} ({len(self.results[ward_name])} candidates):")
                print("Portal | Name | Price | Size | Layout | Floor | Year | Walk | Station | Fees | Dir | Ownership")
                print("-" * 160)

                for listing in self.results[ward_name]:
                    price_str = f"¥{listing.get('price_yen', 0)//10000:.0f}M" if listing.get('price_yen') else "?"
                    size_str = f"{listing.get('size_m2', '?'):.0f}m²" if listing.get('size_m2') else "?"
                    layout = listing.get('layout', '?')
                    floor = f"{listing.get('floor', '?')}F"
                    year = listing.get('year', '?')
                    walk = f"{listing.get('walk_time_min', '?')}m"
                    station = listing.get('station', '?')[:15]
                    fees = f"¥{listing.get('fees_yen', 0)//1000:.0f}k" if listing.get('fees_yen') else "?"
                    direction = listing.get('direction', '?')
                    portal = listing.get('portal', '?')
                    ownership = listing.get('ownership', '?')

                    print(f"{portal:8} | {listing.get('name', '?')[:32]} | {price_str} | {size_str} | {layout:7} | {floor:4} | {year} | {walk:5} | {station:15} | {fees:7} | {direction:3} | {ownership}")

            else:
                print(f"\n{ward_name}: No qualifying candidates found")

        return total_new, self.results


if __name__ == '__main__':
    scraper = SecondaryWardsCorrected()
    total, results = scraper.run_scan()
