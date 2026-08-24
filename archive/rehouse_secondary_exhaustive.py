#!/usr/bin/env python3
"""
SECONDARY WARDS EXHAUSTIVE SCAN - REHOUSE FOCUS
Due to SUUMO rate-limiting (503 errors), prioritizing Rehouse which is responding
- Full pagination across all secondary wards
- Rehouse: Complete listings extraction
- Strict 8-filter criteria
- Deduplication against 126 existing listings
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

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class RehouseSecondaryExhaustive:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en;q=0.9',
        })

        # Ward codes for Rehouse
        self.ward_codes = {
            'Nakano': '13114',
            'Arakawa': '13118',
            'Edogawa': '13123',
            'Ota': '13111',
            'Nerima': '13120',
            'Chuo': '13102',
            'Minato': '13103',
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

        self.existing_listings = self.load_existing_listings()
        print(f"[INFO] Loaded {len(self.existing_listings)} existing listings for deduplication\n")

        self.results = defaultdict(list)

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
                    match = re.search(r'^Add #\d+\s+([^(]+)', line)
                    if match:
                        name = match.group(1).strip()
                        if name and len(name) > 2:
                            existing.add(name)
                            if '・' in name:
                                parts = name.split('・')
                                existing.add(parts[0].strip())
        except:
            pass

        return existing

    def parse_price_yen(self, text: str) -> Optional[int]:
        if not text:
            return None
        try:
            match = re.search(r'(\d+),?(\d{0,3})\s*万', text)
            if match:
                num = match.group(1).replace(',', '')
                return int(num) * 10_000
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

    def parse_fees(self, text: str) -> Optional[int]:
        if not text:
            return None
        try:
            match = re.search(r'(\d+),?(\d{0,3})\s*(?:円|/月)', text)
            if match:
                num = match.group(1).replace(',', '')
                return int(num)
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

    def passes_filters(self, listing: Dict) -> Tuple[bool, Optional[str]]:
        """Check if listing passes all hard filters"""

        if listing.get('price_yen'):
            if listing['price_yen'] < self.filters['price_min_yen']:
                return False, f"Price too low"
            if listing['price_yen'] > self.filters['price_max_yen']:
                return False, f"Price over budget"

        if listing.get('size_m2'):
            if listing['size_m2'] < self.filters['size_min_m2']:
                return False, f"Size too small"

        if listing.get('year'):
            if listing['year'] < self.filters['year_min']:
                return False, f"Pre-1982"

        if listing.get('walk_time_min'):
            if listing['walk_time_min'] > self.filters['walk_max_min']:
                return False, f"Walk time too long"

        if listing.get('floor'):
            if listing['floor'] < self.filters['floor_min']:
                return False, f"Ground floor"

        if listing.get('fees_yen'):
            if listing['fees_yen'] > self.filters['fees_max_yen']:
                return False, f"Fees too high"

        layout = listing.get('layout', '').upper()
        if layout:
            valid = ['1LDK', '2LDK', '3LDK', '4LDK', '2DK', '3DK', '1DK']
            if not any(v in layout for v in valid):
                return False, f"Invalid layout"

        if listing.get('direction', '').upper() in ['N', '北']:
            return False, f"North-only"

        return True, None

    def is_duplicate(self, listing: Dict) -> bool:
        """Check if building already exists"""
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

    def scan_rehouse_ward(self, ward_name: str, ward_code: str) -> List[Dict]:
        """Scan all Rehouse pages for a ward"""
        listings = []
        page = 1
        max_pages = 100
        consecutive_empty = 0

        print(f"  Scanning {ward_name}...", end='', flush=True)

        while page <= max_pages:
            try:
                url = f'https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{ward_code}/'
                params = {} if page == 1 else {'page': page}

                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    print(f" (page {page}: HTTP {resp.status_code})", end='', flush=True)
                    break

                soup = BeautifulSoup(resp.content, 'html.parser')

                # Find all listing links
                listing_links = soup.find_all('a', href=re.compile(r'/bkdetail/'))

                if not listing_links:
                    consecutive_empty += 1
                    if consecutive_empty > 2:
                        break
                else:
                    consecutive_empty = 0
                    print(f" p{page}({len(listing_links)})", end='', flush=True)

                for link in listing_links:
                    try:
                        detail_url = link.get('href', '')
                        if not detail_url.startswith('http'):
                            detail_url = urljoin('https://www.rehouse.co.jp', detail_url)

                        time.sleep(1.5)  # Aggressive rate limiting
                        detail_resp = self.session.get(detail_url, timeout=15)

                        if detail_resp.status_code == 200:
                            listing = self.extract_detail(detail_resp.content, ward_name, detail_url)
                            if listing:
                                passes, _ = self.passes_filters(listing)
                                if passes and not self.is_duplicate(listing):
                                    listings.append(listing)
                    except:
                        continue

                page += 1
                time.sleep(2)  # Aggressive delay between pages

            except Exception as e:
                break

        print(f" ✓ {len(listings)} qualified")
        return listings

    def extract_detail(self, html: bytes, ward_name: str, url: str) -> Optional[Dict]:
        """Extract details from Rehouse listing page"""
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

            # Extract fields
            price_match = re.search(r'(\d+),?(\d{0,3})\s*万', text)
            if price_match:
                listing['price_yen'] = self.parse_price_yen(price_match.group(0))

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
                station = self.parse_station(walk_match.group(0))
                if station:
                    listing['station'] = station
                listing['walk_time_min'] = self.parse_walk_time(walk_match.group(0))

            fees_match = re.search(r'(?:管理費|修繕積立金)[：:]\s*(\d+),?(\d{0,3})\s*(?:円|/月)', text)
            if fees_match:
                listing['fees_yen'] = self.parse_fees(fees_match.group(0))

            direction = self.parse_direction(text)
            if direction:
                listing['direction'] = direction

            if listing.get('name') and len(listing.get('name', '')) > 2:
                return listing

            return None

        except:
            return None

    def run_scan(self):
        """Run exhaustive scan"""
        print("=" * 100)
        print("SECONDARY WARDS EXHAUSTIVE SCAN - REHOUSE FOCUS")
        print("=" * 100)
        print(f"Start: {datetime.now()}")
        print(f"Criteria: ¥1.5M-¥40M | 30m²+ | 1LDK+ | 1982+ | ≤15min walk | 2F+ | ≤¥30k fees")
        print(f"Existing DB: {len(self.existing_listings)} listings")
        print(f"Wards: Nakano, Arakawa, Edogawa, Ota, Nerima, Chuo, Minato\n")

        total_new = 0

        for ward_name in sorted(self.ward_codes.keys()):
            ward_code = self.ward_codes[ward_name]
            rehouse_listings = self.scan_rehouse_ward(ward_name, ward_code)
            self.results[ward_name].extend(rehouse_listings)
            total_new += len(rehouse_listings)

        print(f"\n{'=' * 100}")
        print(f"SCAN COMPLETE")
        print(f"Total new qualified candidates: {total_new}")
        print(f"End: {datetime.now()}\n")

        # Print results
        print("RESULTS:\n")
        for ward_name in sorted(self.results.keys()):
            if self.results[ward_name]:
                print(f"\n{ward_name} ({len(self.results[ward_name])} candidates):")
                print("Name | Price | Size | Layout | Floor | Year | Walk | Station | Fees | Dir")
                print("-" * 120)

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

                    print(f"{listing.get('name', '?')[:30]} | {price_str} | {size_str} | {layout:7} | {floor:4} | {year} | {walk:4} | {station:15} | {fees:7} | {direction}")

        return total_new, self.results


if __name__ == '__main__':
    scraper = RehouseSecondaryExhaustive()
    total, results = scraper.run_scan()
