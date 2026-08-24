#!/usr/bin/env python3
"""
NOMU.COM Optimized Scraper - 10 Wards
Smarter page parsing to reduce detail page fetches
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import sys
from urllib.parse import urljoin
from typing import Dict, List, Tuple, Set
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class NomuOptimizedScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.base_url = "https://www.nomu.com"

        self.wards = {
            'Itabashi': 13119,
            'Katsushika': 13122,
            'Kita': 13117,
            'Koto': 13108,
            'Minato': 13103,
            'Nakano': 13114,
            'Nerima': 13120,
            'Ota': 13111,
            'Setagaya': 13112,
            'Sumida': 13107,
        }

        self.existing_listings = self.load_existing_listings()
        print(f"[INFO] Loaded {len(self.existing_listings)} existing listings")

    def load_existing_listings(self) -> Set[str]:
        listings = set()
        try:
            with open('existing_listings.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    name = line.strip()
                    if name and not name.startswith('HOME') and not name.startswith('SUUMO'):
                        listings.add(name)
        except:
            pass
        return listings

    def extract_price_yen(self, text: str) -> int:
        """Extract price in yen"""
        match = re.search(r'(\d{1,2},?\d{3}|\d{1,4})\s*万', text)
        if match:
            return int(match.group(1).replace(',', '')) * 10_000
        return 0

    def extract_size_m2(self, text: str) -> float:
        """Extract size in m²"""
        match = re.search(r'(\d+\.?\d*)\s*m[²m2]', text)
        if match:
            return float(match.group(1))
        return 0.0

    def extract_year(self, text: str) -> int:
        """Extract year"""
        match = re.search(r'(19|20)(\d{2})\s*年', text)
        if match:
            return int(match.group(1) + match.group(2))
        return 0

    def extract_walk_min(self, text: str) -> int:
        """Extract walk time"""
        times = re.findall(r'(\d+)\s*分', text)
        if times:
            return min(int(t) for t in times)
        return 0

    def extract_floor(self, text: str) -> int:
        """Extract floor number"""
        match = re.search(r'(\d+)\s*[F階]', text)
        if match:
            return int(match.group(1))
        return 0

    def extract_layout(self, text: str) -> str:
        """Extract layout"""
        match = re.search(r'([1-5]L?DK)', text)
        if match:
            return match.group(1)
        match = re.search(r'([1-5]DK)', text)
        if match:
            return match.group(1)
        match = re.search(r'([1-5]R)', text)
        if match:
            return match.group(1)
        return ''

    def extract_fees_yen(self, text: str) -> int:
        """Extract monthly fees"""
        patterns = [
            r'(\d{1,3},?\d{3}|\d{1,5})\s*円',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1).replace(',', ''))
        return 0

    def quick_filter_check(self, listing_html: str) -> Tuple[bool, str]:
        """Quick check if listing might pass filters based on page info"""
        text = listing_html.lower()

        # Check price is in range
        price = self.extract_price_yen(listing_html)
        if price < 1_500_000 or price > 40_000_000:
            return False, "Price out of range"

        # Check size
        size = self.extract_size_m2(listing_html)
        if size < 30:
            return False, "Size < 30m²"

        # Check year
        year = self.extract_year(listing_html)
        if year > 0 and year < 1982:
            return False, "Year < 1982"

        # Check walk
        walk = self.extract_walk_min(listing_html)
        if walk > 15 and walk > 0:
            return False, "Walk > 15min"

        # Check floor
        floor = self.extract_floor(listing_html)
        if floor > 0 and floor < 2:
            return False, "Floor < 2F"

        return True, "PASS"

    def fetch_detail_and_filter(self, listing_url: str, name: str) -> Dict:
        """Fetch detail page and extract full info"""
        data = {
            'name': name,
            'price_yen': 0,
            'size_m2': 0.0,
            'floor': 0,
            'year': 0,
            'walk_min': 0,
            'station': '',
            'fees_yen': 0,
            'layout': '',
            'direction': '',
            'is_freehold': True,
            'url': listing_url,
        }

        try:
            resp = self.session.get(listing_url, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()

            # Extract all fields
            data['price_yen'] = self.extract_price_yen(text)
            data['size_m2'] = self.extract_size_m2(text)
            data['floor'] = self.extract_floor(text)
            data['year'] = self.extract_year(text)
            data['walk_min'] = self.extract_walk_min(text)
            data['layout'] = self.extract_layout(text)
            data['fees_yen'] = self.extract_fees_yen(text)

            # Extract station
            matches = re.findall(r'「([^」]+)」\s*駅', text)
            if matches:
                data['station'] = matches[0]

            # Extract direction
            directions = ['南東', '南西', '北東', '北西', '南', '北', '東', '西']
            for direction in directions:
                if direction in text:
                    data['direction'] = direction
                    break

            # Check freehold
            if '借地権' in text or '借地' in text:
                data['is_freehold'] = False

            time.sleep(0.3)

        except Exception as e:
            print(f"      [Error] {e}")

        return data

    def passes_filters(self, data: Dict) -> bool:
        """Check all filters"""
        if data['price_yen'] < 1_500_000 or data['price_yen'] > 40_000_000:
            return False
        if data['size_m2'] < 30:
            return False
        if data['year'] > 0 and data['year'] < 1982:
            return False
        if data['walk_min'] > 15 and data['walk_min'] > 0:
            return False
        if data['floor'] < 2:
            return False
        if data['fees_yen'] > 30_000 and data['fees_yen'] > 0:
            return False
        if data['direction'] == '北' or data['direction'] == '北北':
            return False
        if not data['is_freehold']:
            return False
        if data['layout'] and 'LDK' in data['layout']:
            match = re.search(r'^(\d+)', data['layout'])
            if match and int(match.group(1)) < 1:
                return False

        return True

    def scrape_ward_all_pages(self, ward_name: str, ward_code: int) -> List[Dict]:
        """Scrape all pages for a ward"""
        results = []
        page = 1

        print(f"\n{'='*100}")
        print(f"WARD: {ward_name} (Code {ward_code})")
        print('='*100)

        while page <= 100:
            url = f"{self.base_url}/mansion/area_tokyo/{ward_code}/?pager_page={page}"

            try:
                print(f"  Page {page:2d}: ", end='', flush=True)
                resp = self.session.get(url, timeout=10)
                resp.encoding = 'utf-8'

                if resp.status_code != 200:
                    print(f"[Status {resp.status_code}]")
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'/mansion/id/'))

                if not links:
                    print("[End]")
                    break

                page_new_count = 0
                for link in links:
                    name = link.get_text(strip=True)
                    if not name or name in self.existing_listings:
                        continue

                    detail_url = urljoin(self.base_url, link.get('href', ''))

                    # Fetch detail and check filters
                    data = self.fetch_detail_and_filter(detail_url, name)

                    if self.passes_filters(data):
                        data['ward'] = ward_name
                        results.append(data)
                        page_new_count += 1

                print(f"{page_new_count} new qualifying")
                page += 1
                time.sleep(0.3)

            except Exception as e:
                print(f"[Error: {e}]")
                break

        return results

    def scrape_all_wards(self) -> List[Dict]:
        """Scrape all 10 wards"""
        all_results = []

        for ward_name in sorted(self.wards.keys()):
            ward_results = self.scrape_ward_all_pages(ward_name, self.wards[ward_name])
            all_results.extend(ward_results)

        return all_results

    def save_results_tsv(self, listings: List[Dict]):
        """Save as tab-separated"""
        with open('NOMU_10WARDS_RESULTS.tsv', 'w', encoding='utf-8') as f:
            # Header
            header = ["Name", "Price (万円)", "Size (m²)", "Floor", "Year", "Walk (min)",
                      "Station", "Fees (¥/mo)", "Layout", "Direction", "Ownership", "Notes"]
            f.write("\t".join(header) + "\n")

            # Rows
            for listing in sorted(listings, key=lambda x: (x['ward'], x['price_yen'])):
                price_man = listing['price_yen'] // 10_000 if listing['price_yen'] > 0 else ''
                ownership = "Freehold" if listing['is_freehold'] else "Leasehold"

                notes = []
                if listing['layout']:
                    notes.append(listing['layout'])
                if listing['size_m2'] > 50:
                    notes.append("Spacious")
                notes_str = "; ".join(notes)

                row = [
                    listing['name'],
                    str(price_man),
                    f"{listing['size_m2']:.1f}" if listing['size_m2'] > 0 else '',
                    f"{listing['floor']}F" if listing['floor'] > 0 else '',
                    str(listing['year']) if listing['year'] > 0 else '',
                    str(listing['walk_min']) if listing['walk_min'] > 0 else '',
                    listing['station'],
                    f"{listing['fees_yen']:,}" if listing['fees_yen'] > 0 else '',
                    listing['layout'],
                    listing['direction'],
                    ownership,
                    notes_str
                ]
                f.write("\t".join(row) + "\n")

        print(f"\n[SUCCESS] Saved to NOMU_10WARDS_RESULTS.tsv")

def main():
    print("\n" + "="*100)
    print("NOMU.COM OPTIMIZED SCRAPER - 10 WARDS")
    print("="*100)

    scraper = NomuOptimizedScraper()
    all_results = scraper.scrape_all_wards()

    print("\n" + "="*100)
    print(f"FINAL: {len(all_results)} new qualifying listings")
    print("="*100)

    if all_results:
        by_ward = defaultdict(list)
        for listing in all_results:
            by_ward[listing['ward']].append(listing)

        print("\nResults by ward:")
        for ward in sorted(by_ward.keys()):
            print(f"  {ward}: {len(by_ward[ward])}")

        scraper.save_results_tsv(all_results)
    else:
        print("\nNo new qualifying listings found.")

if __name__ == '__main__':
    main()
