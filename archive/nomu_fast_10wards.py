#!/usr/bin/env python3
"""
NOMU.COM Fast Scraper - 10 Wards with Threading
Uses concurrent requests to speed up page fetching
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import sys
from urllib.parse import urljoin
from typing import Dict, List, Tuple, Set
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class NomuFastScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.base_url = "https://www.nomu.com"
        self.lock = threading.Lock()

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
        self.results = []

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

    def extract_from_detail_page(self, listing_url: str, name: str) -> Dict:
        """Extract data from detail page"""
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
            text = resp.text

            # Price
            match = re.search(r'(\d{1,2},?\d{3}|\d{1,4})\s*万', text)
            if match:
                data['price_yen'] = int(match.group(1).replace(',', '')) * 10_000

            # Size
            match = re.search(r'(\d+\.?\d*)\s*m[²m2]', text)
            if match:
                data['size_m2'] = float(match.group(1))

            # Year
            match = re.search(r'(19|20)(\d{2})\s*年', text)
            if match:
                data['year'] = int(match.group(1) + match.group(2))

            # Walk
            times = re.findall(r'(\d+)\s*分', text)
            if times:
                data['walk_min'] = min(int(t) for t in times)

            # Floor
            match = re.search(r'(\d+)\s*[F階]', text)
            if match:
                data['floor'] = int(match.group(1))

            # Layout
            match = re.search(r'([1-5]L?DK)', text)
            if match:
                data['layout'] = match.group(1)
            else:
                match = re.search(r'([1-5]DK)', text)
                if match:
                    data['layout'] = match.group(1)

            # Station
            matches = re.findall(r'「([^」]+)」\s*駅', text)
            if matches:
                data['station'] = matches[0]

            # Direction
            for direction in ['南東', '南西', '北東', '北西', '南', '北', '東', '西']:
                if direction in text:
                    data['direction'] = direction
                    break

            # Fees
            match = re.search(r'(\d{1,3},?\d{3}|\d{1,5})\s*円', text)
            if match:
                data['fees_yen'] = int(match.group(1).replace(',', ''))

            # Freehold check
            if '借地権' in text or '借地' in text:
                data['is_freehold'] = False

        except Exception as e:
            pass

        return data

    def passes_filters(self, data: Dict) -> bool:
        """Check if passes all filters"""
        if data['price_yen'] < 1_500_000 or data['price_yen'] > 40_000_000:
            return False
        if data['size_m2'] < 30:
            return False
        if data['year'] > 0 and data['year'] < 1982:
            return False
        if data['walk_min'] > 15 and data['walk_min'] > 0:
            return False
        if data['floor'] > 0 and data['floor'] < 2:
            return False
        if data['fees_yen'] > 0 and data['fees_yen'] > 30_000:
            return False
        if data['direction'] == '北':
            return False
        if not data['is_freehold']:
            return False
        return True

    def process_listing(self, link_elem, ward_name: str):
        """Process a single listing"""
        name = link_elem.get_text(strip=True)
        if not name or name in self.existing_listings:
            return

        detail_url = urljoin(self.base_url, link_elem.get('href', ''))

        # Fetch and check
        data = self.extract_from_detail_page(detail_url, name)

        if self.passes_filters(data):
            data['ward'] = ward_name
            with self.lock:
                self.results.append(data)

    def scrape_ward_pages(self, ward_name: str, ward_code: int, max_pages: int = 100):
        """Scrape all pages for a ward"""
        all_listings = []

        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/mansion/area_tokyo/{ward_code}/?pager_page={page}"

            try:
                resp = self.session.get(url, timeout=10)
                resp.encoding = 'utf-8'

                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'/mansion/id/'))

                if not links:
                    break

                all_listings.extend(links)
                print(f"  {ward_name} Page {page}: {len(links)} listings found", flush=True)

            except:
                break

        print(f"  {ward_name}: Total {len(all_listings)} listings to process")

        # Process all listings for this ward with threads
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for i, link in enumerate(all_listings):
                future = executor.submit(self.process_listing, link, ward_name)
                futures.append(future)

                if (i + 1) % 50 == 0:
                    print(f"    {ward_name}: Submitted {i+1}/{len(all_listings)} listings", flush=True)

            # Wait for completion
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 50 == 0:
                    print(f"    {ward_name}: Completed {completed}/{len(all_listings)}", flush=True)

    def scrape_all_wards(self):
        """Scrape all wards"""
        print("\n" + "="*100)
        print("NOMU.COM FAST SCRAPER - 10 WARDS (with Threading)")
        print("="*100)
        print(f"[INFO] Loaded {len(self.existing_listings)} existing listings\n")

        for ward_name in sorted(self.wards.keys()):
            print(f"\nWARD: {ward_name}")
            print("-" * 50)
            self.scrape_ward_pages(ward_name, self.wards[ward_name])

    def save_results(self):
        """Save as tab-separated"""
        with open('NOMU_10WARDS_RESULTS.tsv', 'w', encoding='utf-8') as f:
            # Header
            header = ["Name", "Price (万円)", "Size (m²)", "Floor", "Year", "Walk (min)",
                      "Station", "Fees (¥/mo)", "Layout", "Direction", "Ownership", "Notes"]
            f.write("\t".join(header) + "\n")

            # Rows
            for listing in sorted(self.results, key=lambda x: (x['ward'], x['price_yen'])):
                price_man = listing['price_yen'] // 10_000 if listing['price_yen'] > 0 else ''
                ownership = "Freehold" if listing['is_freehold'] else "Leasehold"

                notes = []
                if listing['layout']:
                    notes.append(listing['layout'])
                if listing['size_m2'] > 50:
                    notes.append("Spacious")

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
                    ";".join(notes) if notes else ''
                ]
                f.write("\t".join(row) + "\n")

        print(f"\n[SUCCESS] Saved {len(self.results)} results to NOMU_10WARDS_RESULTS.tsv")

def main():
    scraper = NomuFastScraper()
    scraper.scrape_all_wards()

    print("\n" + "="*100)
    print(f"FINAL: {len(scraper.results)} new qualifying listings")
    print("="*100)

    if scraper.results:
        by_ward = defaultdict(list)
        for listing in scraper.results:
            by_ward[listing['ward']].append(listing)

        print("\nResults by ward:")
        for ward in sorted(by_ward.keys()):
            print(f"  {ward}: {len(by_ward[ward])}")

        scraper.save_results()
    else:
        print("No qualifying listings found")

if __name__ == '__main__':
    main()
