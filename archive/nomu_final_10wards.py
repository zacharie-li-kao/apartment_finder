#!/usr/bin/env python3
"""
NOMU.COM Final Scraper - 10 Wards
Proper HTML parsing with BeautifulSoup
"""

import requests
from bs4 import BeautifulSoup
import re
import sys
from urllib.parse import urljoin
from typing import Dict, Set
import json

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class FinalScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.base_url = "https://www.nomu.com"

        # Target 10 wards ONLY
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

        self.existing = self.load_existing()
        self.results = []

    def load_existing(self) -> Set[str]:
        listings = set()
        try:
            with open('existing_listings.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    name = line.strip()
                    if name and not name.startswith('HOME') and not name.startswith('SUUMO'):
                        listings.add(name)
        except:
            pass
        print(f"[INFO] Loaded {len(listings)} existing listings")
        return listings

    def extract_from_detail(self, soup: BeautifulSoup, url: str, name: str, ward: str) -> Dict:
        """Extract data from detail page soup"""
        data = {
            'name': name,
            'ward': ward,
            'url': url,
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
        }

        try:
            # Price: find span.item_price with class num
            price_elem = soup.find(class_='item_price')
            if price_elem:
                num_span = price_elem.find(class_='num')
                if num_span:
                    price_str = num_span.get_text().strip().replace(',', '')
                    try:
                        data['price_yen'] = int(float(price_str)) * 10_000
                    except:
                        pass

            # Get full text for other extractions
            text = soup.get_text()

            # Size: look for "XXm2" or "XXm²"
            size_match = re.search(r'(\d+\.?\d*)\s*m[²2m]', text)
            if size_match:
                data['size_m2'] = float(size_match.group(1))

            # Year: look for YYYY年
            year_match = re.search(r'(19|20)(\d{2})\s*年', text)
            if year_match:
                data['year'] = int(year_match.group(1) + year_match.group(2))

            # Layout: look for nLDK, nDK, nR
            layout_match = re.search(r'([1-5])[LDK]+', text)
            if layout_match:
                data['layout'] = layout_match.group(0)

            # Floor: look for XX階
            floor_match = re.search(r'(\d+)\s*階', text)
            if floor_match:
                data['floor'] = int(floor_match.group(1))

            # Walk time: look for 徒歩X分
            walk_matches = re.findall(r'徒歩\s*(\d+)\s*分', text)
            if walk_matches:
                data['walk_min'] = min(int(w) for w in walk_matches)

            # Station: look for 「駅名」駅
            station_matches = re.findall(r'「([^」]+)」\s*駅', text)
            if station_matches:
                data['station'] = station_matches[0]

            # Direction: look for 向き or just the direction character
            directions = ['南東', '南西', '北東', '北西', '南', '北', '東', '西']
            for direction in directions:
                if direction in text:
                    data['direction'] = direction
                    break

            # Fees: look for "X,XXX円" (monthly fees)
            fees_match = re.search(r'(\d{1,3},?\d{3})\s*円', text)
            if fees_match:
                data['fees_yen'] = int(fees_match.group(1).replace(',', ''))

            # Freehold: check for 借地権 (leasehold)
            if '借地権' in text or '借地' in text:
                data['is_freehold'] = False

        except Exception as e:
            pass

        return data

    def passes_filters(self, data: Dict) -> bool:
        """Check all 8 filters"""
        # 1. Price: ¥1.5M - ¥40M
        if not (1_500_000 <= data['price_yen'] <= 40_000_000):
            return False

        # 2. Size: >= 30m²
        if data['size_m2'] < 30:
            return False

        # 3. Year: >= 1982
        if data['year'] > 0 and data['year'] < 1982:
            return False

        # 4. Walk: <= 15 min
        if data['walk_min'] > 15 and data['walk_min'] > 0:
            return False

        # 5. Floor: >= 2F
        if data['floor'] > 0 and data['floor'] < 2:
            return False

        # 6. Fees: <= ¥30k/month
        if data['fees_yen'] > 0 and data['fees_yen'] > 30_000:
            return False

        # 7. Direction: Not north-only (北向きのみ)
        if data['direction'] == '北':
            return False

        # 8. Freehold only (所有権)
        if not data['is_freehold']:
            return False

        return True

    def fetch_detail_soup(self, url: str) -> BeautifulSoup:
        """Fetch and parse detail page"""
        try:
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'utf-8'
            return BeautifulSoup(resp.text, 'html.parser')
        except:
            return None

    def save_results(self):
        """Save as tab-separated"""
        with open('NOMU_10WARDS_RESULTS.tsv', 'w', encoding='utf-8') as f:
            header = ["Name", "Price (万円)", "Size (m²)", "Floor", "Year", "Walk (min)",
                      "Station", "Fees (¥/mo)", "Layout", "Direction", "Ownership", "Notes"]
            f.write("\t".join(header) + "\n")

            for r in sorted(self.results, key=lambda x: (x['ward'], x['price_yen'])):
                price_man = r['price_yen'] // 10_000 if r['price_yen'] > 0 else ''
                owner = "Freehold" if r['is_freehold'] else "Leasehold"
                notes = []
                if r['layout']:
                    notes.append(r['layout'])
                if r['size_m2'] > 50:
                    notes.append("Spacious")

                row = [
                    r['name'],
                    str(price_man),
                    f"{r['size_m2']:.1f}" if r['size_m2'] > 0 else '',
                    f"{r['floor']}F" if r['floor'] > 0 else '',
                    str(r['year']) if r['year'] > 0 else '',
                    str(r['walk_min']) if r['walk_min'] > 0 else '',
                    r['station'],
                    f"{r['fees_yen']:,}" if r['fees_yen'] > 0 else '',
                    r['layout'],
                    r['direction'],
                    owner,
                    ";".join(notes) if notes else ''
                ]
                f.write("\t".join(row) + "\n")

        print(f"\n✓ Saved {len(self.results)} results to NOMU_10WARDS_RESULTS.tsv")

    def scrape_ward(self, ward_name: str, ward_code: int):
        """Scrape all pages for one ward"""
        print(f"\n{ward_name:12s}: ", end='', flush=True)
        page = 1
        ward_count = 0

        while page <= 150:
            url = f"{self.base_url}/mansion/area_tokyo/{ward_code}/?pager_page={page}"

            try:
                resp = self.session.get(url, timeout=10)
                resp.encoding = 'utf-8'

                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'/mansion/id/'))

                if not links:
                    print("[END]", end='')
                    break

                page_count = 0
                for link in links:
                    name = link.get_text(strip=True)
                    if not name or name in self.existing:
                        continue

                    detail_url = urljoin(self.base_url, link.get('href', ''))
                    detail_soup = self.fetch_detail_soup(detail_url)

                    if detail_soup:
                        data = self.extract_from_detail(detail_soup, detail_url, name, ward_name)

                        if self.passes_filters(data):
                            self.results.append(data)
                            page_count += 1
                            ward_count += 1

                            # Periodic save every 50 results
                            if len(self.results) % 50 == 0:
                                self.save_results()

                if page_count > 0 or page <= 5:
                    print(f"p{page}({page_count}) ", end='', flush=True)
                else:
                    print(".", end='', flush=True)

                page += 1

            except Exception as e:
                print(f"[E:{str(e)[:10]}]", end='', flush=True)
                break

        print(f"[{ward_count}]")

    def scrape_all(self):
        """Scrape all 10 wards"""
        print("="*80)
        print("NOMU.COM - 10 WARDS FINAL SCRAPER")
        print("Targets: Itabashi, Katsushika, Kita, Koto, Minato, Nakano, Nerima, Ota, Setagaya, Sumida")
        print("="*80)

        for ward_name in sorted(self.wards.keys()):
            self.scrape_ward(ward_name, self.wards[ward_name])

        print("\n" + "="*80)
        print(f"FINAL: {len(self.results)} NEW qualifying listings")
        print("="*80)

        if self.results:
            by_ward = {}
            for r in self.results:
                by_ward[r['ward']] = by_ward.get(r['ward'], 0) + 1

            print("\nBy ward:")
            for ward in sorted(by_ward.keys()):
                print(f"  {ward}: {by_ward[ward]}")

            self.save_results()
        else:
            print("No qualifying listings found.")

if __name__ == '__main__':
    scraper = FinalScraper()
    scraper.scrape_all()
