#!/usr/bin/env python3
"""
NOMU.COM Comprehensive Scraper - 10 Ward Deep Crawl
Scrapes: Itabashi, Katsushika, Kita, Koto, Minato, Nakano, Nerima, Ota, Setagaya, Sumida
Applies all 8 filter criteria, deduplicates against 155 existing listings, outputs tab-separated results
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import sys
from urllib.parse import urljoin
from typing import Dict, List, Tuple, Set
from collections import defaultdict

# Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

class NomuComprehensiveScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.base_url = "https://www.nomu.com"

        # Target 10 wards only
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

        # Filter criteria (8 total)
        self.criteria = {
            'price_min_yen': 1_500_000,
            'price_max_yen': 40_000_000,
            'size_min_m2': 30.0,
            'year_min': 1982,
            'walk_max_min': 15,
            'floor_min': 2,
            'fees_max_yen': 30_000,
            'no_north_only': True
        }

        # Load existing listings for deduplication
        self.existing_listings = self.load_existing_listings()
        print(f"[INFO] Loaded {len(self.existing_listings)} existing listings for deduplication")

    def load_existing_listings(self) -> Set[str]:
        """Load existing listings from file"""
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

    def parse_price_yen(self, text: str) -> Tuple[int, str]:
        """Extract price in yen. Returns (price_yen, display_str)"""
        try:
            # Look for ¥XXX万 or XXX万円
            match = re.search(r'(\d{1,2},?\d{3}|\d{1,4})\s*万?円?', text)
            if match:
                price_str = match.group(1).replace(',', '')
                # Convert to yen (万 = 10,000)
                price_yen = int(float(price_str)) * 10_000
                display = f"{price_str}万円"
                return price_yen, display
        except:
            pass
        return 0, ''

    def parse_size_m2(self, text: str) -> Tuple[float, str]:
        """Extract size in m². Returns (size_m2, display_str)"""
        try:
            match = re.search(r'(\d+\.?\d*)\s*m[²²m2]', text)
            if match:
                size = float(match.group(1))
                return size, f"{match.group(1)}m²"
        except:
            pass
        return 0.0, ''

    def parse_year(self, text: str) -> Tuple[int, str]:
        """Extract year built. Returns (year, display_str)"""
        try:
            # Try Japanese year format first
            match = re.search(r'(19|20)(\d{2})\s*年', text)
            if match:
                year = int(match.group(1) + match.group(2))
                month_match = re.search(r'19(\d{2})年(\d{1,2})月|20(\d{2})年(\d{1,2})月', text)
                if month_match:
                    return year, f"{year}年{month_match.group(2) or month_match.group(4)}月"
                return year, f"{year}年"
        except:
            pass
        return 0, ''

    def parse_floor(self, text: str) -> Tuple[int, str]:
        """Extract floor number. Returns (floor_num, display_str)"""
        try:
            # Look for patterns like "3/6" or "3階/6階"
            match = re.search(r'(\d+)\s*(?:階|F)\s*[/\/]\s*(\d+)?', text)
            if match:
                floor_num = int(match.group(1))
                total = match.group(2)
                if total:
                    return floor_num, f"{match.group(1)}F/{total}F"
                return floor_num, f"{match.group(1)}F"
        except:
            pass
        return 0, ''

    def parse_walk_min(self, text: str) -> Tuple[int, str]:
        """Extract minimum walk time in minutes. Returns (walk_min, display_str)"""
        try:
            # Find all walk times and take minimum
            times = re.findall(r'(\d+)\s*(?:分|min)(?:.*?駅)?', text)
            if times:
                min_time = min(int(t) for t in times)
                return min_time, f"{min_time}分"
        except:
            pass
        return 0, ''

    def parse_station(self, text: str) -> str:
        """Extract nearest station name"""
        try:
            # Look for 「駅名」駅 pattern
            matches = re.findall(r'「([^」]+)」\s*駅', text)
            if matches:
                return matches[0]
            # Fallback: any text before 駅
            match = re.search(r'([ぁ-ん一-龠ァ-ヴー々〆〤a-zA-Z0-9]+)\s*駅', text)
            if match:
                return match.group(1)
        except:
            pass
        return ''

    def parse_fees_yen(self, text: str) -> Tuple[int, str]:
        """Extract monthly fees (管理費 + 修繕積立金). Returns (fees_yen, display_str)"""
        try:
            # Look for patterns like "25,000円/月" or "管理費20,000円"
            patterns = [
                r'(?:管理費|月額)[\s:：]*(\d{1,3},?\d{3}|\d{1,5})\s*円',
                r'(\d{1,3},?\d{3}|\d{1,5})\s*円\s*[/／]?\s*月',
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    fee_str = match.group(1).replace(',', '')
                    fee_yen = int(float(fee_str))
                    return fee_yen, f"{match.group(1)}円"
        except:
            pass
        return 0, ''

    def parse_layout(self, text: str) -> str:
        """Extract layout (1LDK, 2LDK, etc.)"""
        try:
            match = re.search(r'([1-5])[LDK]+', text)
            if match:
                return match.group(0)
        except:
            pass
        return ''

    def parse_direction(self, text: str) -> str:
        """Extract direction/orientation"""
        directions = ['南東', '南西', '北東', '北西', '南', '北', '東', '西']
        for direction in directions:
            if direction in text:
                return direction
        return ''

    def is_freehold(self, text: str) -> bool:
        """Check if freehold (所有権) not leasehold (借地権)"""
        # Default to True if no leasehold indicator found
        if '借地権' in text or '借地' in text:
            return False
        return True

    def is_vacant(self, text: str) -> bool:
        """Check if vacant (空家) vs owner-occupied"""
        if '空家' in text or '空き家' in text:
            return True
        if 'オーナーチェンジ' in text:
            return False
        return None

    def is_north_only(self, direction: str) -> bool:
        """Check if ONLY north-facing"""
        if direction == '北':
            return True
        if direction == '北東' or direction == '北西':
            return False
        return False

    def passes_all_filters(self, data: Dict) -> Tuple[bool, List[str]]:
        """Check all 8 filter criteria. Returns (passes, failure_reasons)"""
        failures = []

        # 1. Price filter
        if data['price_yen'] < self.criteria['price_min_yen']:
            failures.append(f"Price ¥{data['price_yen']:,} < ¥1.5M")
        elif data['price_yen'] > self.criteria['price_max_yen']:
            failures.append(f"Price ¥{data['price_yen']:,} > ¥40M")

        # 2. Size filter
        if data['size_m2'] < self.criteria['size_min_m2']:
            failures.append(f"Size {data['size_m2']}m² < 30m²")

        # 3. Year filter
        if data['year'] > 0 and data['year'] < self.criteria['year_min']:
            failures.append(f"Year {data['year']} < 1982")

        # 4. Walk time filter
        if data['walk_min'] > self.criteria['walk_max_min']:
            failures.append(f"Walk {data['walk_min']}min > 15min")

        # 5. Floor filter
        if data['floor_num'] < self.criteria['floor_min']:
            failures.append(f"Floor {data['floor_num']}F < 2F")

        # 6. Fees filter
        if data['fees_yen'] > 0 and data['fees_yen'] > self.criteria['fees_max_yen']:
            failures.append(f"Fees ¥{data['fees_yen']:,} > ¥30k")

        # 7. No north-only filter
        if self.is_north_only(data['direction']):
            failures.append("North-facing only")

        # 8. Freehold only
        if not data['is_freehold']:
            failures.append("Leasehold (借地権)")

        # Layout check (1LDK minimum)
        if data['layout'] and 'LDK' in data['layout']:
            match = re.search(r'^(\d+)', data['layout'])
            if match and int(match.group(1)) < 1:
                failures.append(f"Layout {data['layout']} < 1LDK")

        return len(failures) == 0, failures

    def extract_detail_page_data(self, detail_url: str) -> Dict:
        """Fetch and parse detail page. Returns dict with all extracted fields"""
        data = {
            'name': '',
            'price_yen': 0,
            'price_str': '',
            'size_m2': 0.0,
            'size_str': '',
            'floor_num': 0,
            'floor_str': '',
            'year': 0,
            'year_str': '',
            'walk_min': 0,
            'walk_str': '',
            'station': '',
            'fees_yen': 0,
            'fees_str': '',
            'layout': '',
            'direction': '',
            'is_freehold': True,
            'is_vacant': None,
            'url': detail_url,
        }

        try:
            resp = self.session.get(detail_url, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()

            # Extract name from title or first heading
            title_tag = soup.find('h1') or soup.find('title')
            if title_tag:
                data['name'] = title_tag.get_text(strip=True)

            # Extract all fields
            data['price_yen'], data['price_str'] = self.parse_price_yen(text)
            data['size_m2'], data['size_str'] = self.parse_size_m2(text)
            data['floor_num'], data['floor_str'] = self.parse_floor(text)
            data['year'], data['year_str'] = self.parse_year(text)
            data['walk_min'], data['walk_str'] = self.parse_walk_min(text)
            data['station'] = self.parse_station(text)
            data['fees_yen'], data['fees_str'] = self.parse_fees_yen(text)
            data['layout'] = self.parse_layout(text)
            data['direction'] = self.parse_direction(text)
            data['is_freehold'] = self.is_freehold(text)
            data['is_vacant'] = self.is_vacant(text)

            time.sleep(0.3)  # Rate limit as requested

        except Exception as e:
            print(f"    [Error fetching detail] {e}")

        return data

    def scrape_ward_all_pages(self, ward_name: str, ward_code: int) -> List[Dict]:
        """Scrape all pages for a ward"""
        results = []
        page = 1

        print(f"\n{'='*100}")
        print(f"WARD: {ward_name} (Code {ward_code})")
        print('='*100)

        while page <= 100:  # Safety limit
            url = f"{self.base_url}/mansion/area_tokyo/{ward_code}/?pager_page={page}"

            try:
                print(f"  Page {page:2d}: ", end='', flush=True)
                resp = self.session.get(url, timeout=10)
                resp.encoding = 'utf-8'

                if resp.status_code != 200:
                    print(f"[Status {resp.status_code}]")
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find all listing links
                links = soup.find_all('a', href=re.compile(r'/mansion/id/'))

                if not links:
                    print("[End of listings]")
                    break

                page_new_count = 0
                for link in links:
                    name = link.get_text(strip=True)
                    if not name:
                        continue

                    # Skip if already in existing listings
                    if name in self.existing_listings:
                        continue

                    # Get detail URL
                    detail_url = urljoin(self.base_url, link.get('href', ''))

                    # Fetch and parse detail page
                    data = self.extract_detail_page_data(detail_url)
                    data['name'] = name
                    data['ward'] = ward_name

                    # Check if passes all filters
                    passes, failures = self.passes_all_filters(data)
                    if passes:
                        results.append(data)
                        page_new_count += 1

                print(f"{page_new_count} new passed | Total links: {len(links)}")
                page += 1
                time.sleep(0.3)  # Rate limit between pages

            except Exception as e:
                print(f"[Error: {e}]")
                break

        return results

    def scrape_all_wards(self) -> List[Dict]:
        """Scrape all 10 target wards"""
        all_results = []

        for ward_name, ward_code in sorted(self.wards.items()):
            ward_results = self.scrape_ward_all_pages(ward_name, ward_code)
            all_results.extend(ward_results)

        return all_results

    def output_tab_separated(self, listings: List[Dict]) -> str:
        """Format results as tab-separated table"""
        lines = []

        # Header
        header = "\t".join([
            "Name",
            "Price (万円)",
            "Size (m²)",
            "Floor",
            "Year",
            "Walk (min)",
            "Station",
            "Fees (¥/mo)",
            "Layout",
            "Direction",
            "Ownership",
            "Occupancy",
            "Notes"
        ])
        lines.append(header)

        # Rows
        for listing in listings:
            # Extract price in 万 format
            price_man = listing['price_yen'] // 10_000 if listing['price_yen'] > 0 else ''

            # Ownership
            ownership = "Freehold" if listing['is_freehold'] else "Leasehold"

            # Occupancy
            occupancy = "Vacant" if listing['is_vacant'] else ("Owner-change" if listing['is_vacant'] == False else "Unknown")

            # Notes
            notes = []
            if listing['layout']:
                notes.append(listing['layout'])
            if listing['size_m2'] > 50:
                notes.append("Spacious")
            notes_str = "; ".join(notes) if notes else ""

            row = [
                listing['name'],
                str(price_man) if price_man else '',
                f"{listing['size_m2']:.1f}" if listing['size_m2'] > 0 else '',
                listing['floor_str'],
                str(listing['year']) if listing['year'] > 0 else '',
                str(listing['walk_min']) if listing['walk_min'] > 0 else '',
                listing['station'],
                f"{listing['fees_yen']:,}" if listing['fees_yen'] > 0 else '',
                listing['layout'],
                listing['direction'],
                ownership,
                occupancy,
                notes_str
            ]

            lines.append("\t".join(row))

        return "\n".join(lines)

    def save_results(self, listings: List[Dict], filename: str = 'NOMU_10WARDS_RESULTS.tsv'):
        """Save results to file"""
        output = self.output_tab_separated(listings)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(output)

        print(f"\n[SUCCESS] Results saved to {filename}")
        print(f"Total new listings: {len(listings)}")

def main():
    print("\n" + "="*100)
    print("NOMU.COM COMPREHENSIVE SCRAPER - 10 WARDS")
    print("Wards: Itabashi, Katsushika, Kita, Koto, Minato, Nakano, Nerima, Ota, Setagaya, Sumida")
    print("="*100)

    scraper = NomuComprehensiveScraper()

    print(f"\nFilter Criteria (8 total):")
    print(f"  1. Price: ¥1.5M - ¥40M")
    print(f"  2. Size: ≥30m²")
    print(f"  3. Year: ≥1982 (新耐震基準)")
    print(f"  4. Walk: ≤15 min to station")
    print(f"  5. Floor: ≥2F")
    print(f"  6. Fees: ≤¥30k/month")
    print(f"  7. Direction: Not north-only (北向きのみ)")
    print(f"  8. Ownership: Freehold (所有権) only")
    print(f"  9. Layout: ≥1LDK")
    print(f"  10. Dedup: Against {len(scraper.existing_listings)} existing listings\n")

    # Scrape all wards
    all_results = scraper.scrape_all_wards()

    # Save results
    print("\n" + "="*100)
    print(f"FINAL RESULTS: {len(all_results)} NEW qualifying listings")
    print("="*100)

    if all_results:
        # Group by ward
        by_ward = defaultdict(list)
        for listing in all_results:
            by_ward[listing['ward']].append(listing)

        print("\nBy ward:")
        for ward in sorted(by_ward.keys()):
            print(f"  {ward}: {len(by_ward[ward])}")

        scraper.save_results(all_results)

        # Print preview
        print("\n[PREVIEW] First 3 listings:")
        print(scraper.output_tab_separated(all_results[:3]))
    else:
        print("\nNo new qualifying listings found.")

if __name__ == '__main__':
    main()
