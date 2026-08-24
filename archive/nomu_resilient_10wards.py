#!/usr/bin/env python3
"""
NOMU.COM Resilient Scraper - 10 Wards
Saves results incrementally. Only targets: Itabashi, Katsushika, Kita, Koto, Minato, Nakano, Nerima, Ota, Setagaya, Sumida
"""

import requests
from bs4 import BeautifulSoup
import re
import sys
from urllib.parse import urljoin
from typing import Dict, List, Set
import json

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class ResilientScraper:
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
        print(f"Loaded {len(self.existing)} existing listings")
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
        return listings

    def extract_fields(self, text: str) -> Dict:
        """Extract all fields from detail page text"""
        data = {
            'price_yen': 0, 'size_m2': 0.0, 'floor': 0, 'year': 0,
            'walk_min': 0, 'station': '', 'fees_yen': 0, 'layout': '',
            'direction': '', 'is_freehold': True
        }

        # Price: ¥XXX万円
        m = re.search(r'(\d{1,2},?\d{3}|\d{1,4})\s*万', text)
        if m:
            data['price_yen'] = int(m.group(1).replace(',', '')) * 10_000

        # Size: XXm²
        m = re.search(r'(\d+\.?\d*)\s*m[²m2]', text)
        if m:
            data['size_m2'] = float(m.group(1))

        # Year: 19XX年 or 20XX年
        m = re.search(r'(19|20)(\d{2})\s*年', text)
        if m:
            data['year'] = int(m.group(1) + m.group(2))

        # Walk: XX分
        times = re.findall(r'(\d+)\s*分', text)
        if times:
            data['walk_min'] = min(int(t) for t in times)

        # Floor: XX階 or XF
        m = re.search(r'(\d+)\s*(?:階|F)', text)
        if m:
            data['floor'] = int(m.group(1))

        # Layout: nLDK
        m = re.search(r'([1-5])[LDK]+', text)
        if m:
            data['layout'] = m.group(0)

        # Station
        matches = re.findall(r'「([^」]+)」\s*駅', text)
        if matches:
            data['station'] = matches[0]

        # Direction
        for d in ['南東', '南西', '北東', '北西', '南', '北', '東', '西']:
            if d in text:
                data['direction'] = d
                break

        # Fees
        m = re.search(r'(\d{1,3},?\d{3}|\d{1,5})\s*円', text)
        if m:
            data['fees_yen'] = int(m.group(1).replace(',', ''))

        # Freehold check
        if '借地権' in text or '借地' in text:
            data['is_freehold'] = False

        return data

    def passes_filters(self, data: Dict) -> bool:
        """Check all 8 filters"""
        if not (1_500_000 <= data['price_yen'] <= 40_000_000):
            return False
        if data['size_m2'] < 30:
            return False
        if data['year'] > 0 and data['year'] < 1982:
            return False
        if 0 < data['walk_min'] > 15:
            return False
        if data['floor'] > 0 and data['floor'] < 2:
            return False
        if 0 < data['fees_yen'] > 30_000:
            return False
        if data['direction'] == '北':
            return False
        if not data['is_freehold']:
            return False
        return True

    def fetch_detail(self, url: str, name: str, ward: str) -> Dict:
        """Fetch detail page"""
        try:
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'utf-8'
            data = self.extract_fields(resp.text)
            data['name'] = name
            data['ward'] = ward
            data['url'] = url
            return data
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

        print(f"✓ Saved {len(self.results)} results to NOMU_10WARDS_RESULTS.tsv")

    def scrape_ward(self, ward_name: str, ward_code: int):
        """Scrape all pages for one ward"""
        print(f"\n{ward_name}:", end='', flush=True)
        page = 1
        ward_count = 0

        while page <= 100:
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

                page_count = 0
                for link in links:
                    name = link.get_text(strip=True)
                    if not name or name in self.existing:
                        continue

                    detail_url = urljoin(self.base_url, link.get('href', ''))
                    data = self.fetch_detail(detail_url, name, ward_name)

                    if data and self.passes_filters(data):
                        self.results.append(data)
                        page_count += 1
                        ward_count += 1

                        # Save periodically (every 50 results)
                        if len(self.results) % 50 == 0:
                            self.save_results()

                print(f" p{page}({page_count})", end='', flush=True)
                page += 1

            except Exception as e:
                print(f" ERR:{e}", end='', flush=True)
                break

        print(f" TOTAL:{ward_count}")

    def scrape_all(self):
        """Scrape all 10 wards"""
        print("="*80)
        print("NOMU.COM - 10 WARDS RESILIENT SCRAPER")
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

if __name__ == '__main__':
    scraper = ResilientScraper()
    scraper.scrape_all()
