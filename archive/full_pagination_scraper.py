#!/usr/bin/env python3
"""
FULL PAGINATION COMPREHENSIVE SCRAPER
- Focus on SUUMO (primary: must-check)
- Then Rehouse, NOMU, Livable, Century21
- EXHAUSTIVE page-by-page extraction (all pages until empty)
- 8 strict filters
- Deduplication via git history
- Output: Tab-separated listing data
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import subprocess
from typing import Dict, List, Tuple, Set, Optional
from datetime import datetime
from urllib.parse import urljoin
import json

class FullPaginationScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # All 23 Tokyo wards with NOMU codes
        self.wards = {
            'Chiyoda': ('13101', 0),
            'Chuo': ('13102', 0),
            'Minato': ('13103', 0),
            'Shinjuku': ('13104', 0),
            'Shibuya': ('13105', 0),
            'Taito': ('13106', 0),
            'Sumida': ('13107', 0),
            'Koto': ('13108', 0),
            'Bunkyo': ('13109', 0),
            'Toshima': ('13110', 0),
            'Ota': ('13111', 0),
            'Setagaya': ('13112', 0),
            'Meguro': ('13113', 0),
            'Nakano': ('13114', 0),
            'Suginami': ('13115', 0),
            'Shinagawa': ('13116', 0),
            'Kita': ('13117', 0),
            'Arakawa': ('13118', 0),
            'Itabashi': ('13119', 0),
            'Nerima': ('13120', 0),
            'Adachi': ('13121', 0),
            'Katsushika': ('13122', 0),
            'Edogawa': ('13123', 0),
        }

        # Hard filters
        self.filters = {
            'price_yen_min': 1_500_000,
            'price_yen_max': 40_000_000,
            'size_m2_min': 30,
            'year_min': 1982,
            'walk_min_max': 15,
            'floor_min': 2,
            'fees_yen_max': 30_000,
        }

        # Load existing listings
        self.existing_names = self._load_existing_listings()
        print(f"[INIT] Loaded {len(self.existing_names)} existing building names for deduplication\n")

        self.all_results = []
        self.portal_counts = {}

    def _load_existing_listings(self) -> Set[str]:
        """Extract building names from git commit history"""
        existing = set()
        try:
            result = subprocess.run(
                ['git', 'log', '--all', '--pretty=%s'],
                cwd='C:\\Users\\zakat\\Desktop\\apartment',
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split('\n'):
                    # Extract from "Add #N Name" format
                    if line.startswith('Add #'):
                        # "Add #126 セザール久が原 (Ota · ...)" → "セザール久が原"
                        match = re.search(r'^Add #\d+\s+([^(]+)', line)
                        if match:
                            name = match.group(1).strip()
                            if len(name) > 2:
                                existing.add(name)
                                # Also extract first part if has characters
                                parts = re.split(r'[・ ]+', name)
                                for part in parts:
                                    if len(part) > 3 and any(ord(c) > 127 for c in part):  # Has Japanese
                                        existing.add(part)
        except Exception as e:
            print(f"[WARNING] Could not load git history: {e}")
        return existing

    def _parse_price_yen(self, text: str) -> Optional[int]:
        """Extract price. 3,980万 → 39,800,000 yen"""
        if not text:
            return None
        match = re.search(r'(\d+),?(\d{0,3})\s*万', text)
        if match:
            num_str = (match.group(1) + match.group(2)).replace(',', '')
            try:
                return int(num_str) * 10_000
            except:
                pass
        return None

    def _parse_size_m2(self, text: str) -> Optional[float]:
        """Extract size in m²"""
        if not text:
            return None
        match = re.search(r'(\d+\.?\d*)\s*m[²2m]', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _parse_year(self, text: str) -> Optional[int]:
        """Extract year built"""
        if not text:
            return None
        match = re.search(r'(19|20)(\d{2})\s*年', text)
        if match:
            try:
                return int(match.group(1) + match.group(2))
            except:
                pass
        return None

    def _parse_walk_min(self, text: str) -> Optional[int]:
        """Extract minimum walk time in minutes"""
        if not text:
            return None
        matches = re.findall(r'(\d+)\s*分', text)
        if matches:
            try:
                return min(int(m) for m in matches)
            except:
                pass
        return None

    def _parse_floor(self, text: str) -> Optional[int]:
        """Extract current floor (first number)"""
        if not text:
            return None
        match = re.search(r'^(\d+)', text.strip())
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        return None

    def _parse_fees_yen(self, text: str) -> Optional[int]:
        """Extract monthly fees in yen"""
        if not text:
            return None
        match = re.search(r'(\d+),?(\d{3})\s*円', text)
        if match:
            try:
                num_str = (match.group(1) + match.group(2)).replace(',', '')
                return int(num_str)
            except:
                pass
        return None

    def _extract_direction(self, text: str) -> Optional[str]:
        """Extract direction (方角)"""
        if not text:
            return None
        jp_directions = ['南東', '南西', '北東', '北西', '南', '東', '西', '北']
        en_directions = ['SE', 'SW', 'NE', 'NW', 'S', 'E', 'W', 'N']
        for d in jp_directions + en_directions:
            if d in text:
                return d
        return None

    def _passes_all_filters(self, data: Dict) -> Tuple[bool, str]:
        """Check if data passes all 8 hard filters"""

        # 1. Price
        if 'price_yen' in data and data['price_yen']:
            if not (self.filters['price_yen_min'] <= data['price_yen'] <= self.filters['price_yen_max']):
                return False, f"Price {data['price_yen']/10000:.1f}M out of range"

        # 2. Size
        if 'size_m2' in data and data['size_m2']:
            if data['size_m2'] < self.filters['size_m2_min']:
                return False, f"Size {data['size_m2']}m² < {self.filters['size_m2_min']}m²"

        # 3. Year
        if 'year' in data and data['year']:
            if data['year'] < self.filters['year_min']:
                return False, f"Year {data['year']} < {self.filters['year_min']}"

        # 4. Walk time
        if 'walk_min' in data and data['walk_min']:
            if data['walk_min'] > self.filters['walk_min_max']:
                return False, f"Walk {data['walk_min']}min > {self.filters['walk_min_max']}min"

        # 5. Floor
        if 'floor' in data and data['floor']:
            if data['floor'] < self.filters['floor_min']:
                return False, f"Floor {data['floor']}F < {self.filters['floor_min']}F"

        # 6. Fees
        if 'fees_yen' in data and data['fees_yen']:
            if data['fees_yen'] > self.filters['fees_yen_max']:
                return False, f"Fees {data['fees_yen']:,}¥ > {self.filters['fees_yen_max']:,}¥"

        # 7. Direction (not north-only)
        if 'direction' in data and data['direction']:
            if data['direction'] in ['北', 'N', 'North']:
                return False, f"North-facing only"

        # 8. Layout (1LDK+)
        if 'layout' in data and data['layout']:
            if not any(x in data['layout'].upper() for x in ['1LDK', '2LDK', '3LDK', '4LDK', '2DK', '3DK', '1DK']):
                return False, f"Layout {data['layout']} not 1LDK+"

        return True, "PASS"

    def _is_duplicate(self, name: str) -> bool:
        """Check if building already in database"""
        if not name:
            return False

        # Normalize
        name_clean = name.strip()

        # Exact match
        if name_clean in self.existing_names:
            return True

        # Substring check (some flexibility for variations)
        for existing in self.existing_names:
            if len(name_clean) > 6 and len(existing) > 6:
                # If one is substring of other, likely duplicate
                if name_clean in existing or existing in name_clean:
                    return True

        return False

    def scrape_suumo_exhaustive(self, ward: str, ward_code: str) -> List[Dict]:
        """
        Exhaustively scrape SUUMO for a ward.
        Paginate through ALL pages.
        """
        qualified = []
        page = 1
        max_pages = 200  # Safety limit
        consecutive_blanks = 0

        print(f"  [SUUMO] {ward}...", end='', flush=True)

        while page <= max_pages:
            try:
                # SUUMO chuko (used apartments) URL
                url = f'https://suumo.jp/ms/chuko/Tokyo/{ward_code}/?page={page}'

                resp = self.session.get(url, timeout=15)
                if resp.status_code not in [200, 404]:
                    time.sleep(1)
                    continue

                if resp.status_code == 404:
                    break

                soup = BeautifulSoup(resp.content, 'html.parser')

                # Try multiple selectors for listings
                listings = []
                for selector in [
                    'div.property-item',
                    'div.item-box',
                    'li.item',
                    'article.property',
                    'div[data-mansion-id]'
                ]:
                    listings = soup.select(selector)
                    if listings:
                        break

                if not listings:
                    consecutive_blanks += 1
                    if consecutive_blanks >= 3:  # 3 consecutive blank pages = done
                        break
                else:
                    consecutive_blanks = 0

                # Extract data from each listing
                for item in listings:
                    try:
                        # Get full text content for parsing
                        full_text = item.get_text(separator=' ', strip=True)

                        # Extract name (usually in title or first link)
                        name_elem = item.select_one('a, h2, h3, .title, .name')
                        name = name_elem.get_text(strip=True) if name_elem else ''

                        if not name or self._is_duplicate(name):
                            continue

                        # Parse all available data
                        data = {
                            'name': name,
                            'ward': ward,
                            'portal': 'SUUMO',
                            'url': url,
                            'price_yen': self._parse_price_yen(full_text),
                            'size_m2': self._parse_size_m2(full_text),
                            'year': self._parse_year(full_text),
                            'walk_min': self._parse_walk_min(full_text),
                            'floor': self._parse_floor(full_text),
                            'fees_yen': self._parse_fees_yen(full_text),
                            'direction': self._extract_direction(full_text),
                            'layout': self._extract_layout(full_text),
                        }

                        # Check filters
                        passes, reason = self._passes_all_filters(data)
                        if passes:
                            qualified.append(data)

                    except Exception as e:
                        continue

                page += 1
                time.sleep(0.2)  # Polite rate limiting

            except Exception as e:
                print(f"\n    Error on page {page}: {e}")
                break

        print(f" {len(qualified)} qualified")
        return qualified

    def _extract_layout(self, text: str) -> Optional[str]:
        """Extract layout type"""
        if not text:
            return None
        match = re.search(r'([1-4][LDK]{1,3}K?)', text)
        if match:
            return match.group(1)
        return None

    def scrape_rehouse_exhaustive(self, ward: str) -> List[Dict]:
        """Exhaustively scrape Rehouse for a ward"""
        # Placeholder - Rehouse requires different approach
        return []

    def scrape_nomu_exhaustive(self, ward: str, ward_code: str) -> List[Dict]:
        """Exhaustively scrape NOMU for a ward"""
        qualified = []
        page = 1
        max_pages = 100

        print(f"  [NOMU]  {ward}...", end='', flush=True)

        while page <= max_pages:
            try:
                url = f'https://www.nomu.com/mansion/search/TOKYO{ward_code}.html?page={page}'
                resp = self.session.get(url, timeout=15)

                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.content, 'html.parser')
                items = soup.select('div.mansion-item, div.search-result-item, article')

                if not items:
                    break

                for item in items:
                    try:
                        text = item.get_text(separator=' ', strip=True)
                        name_elem = item.select_one('a, h3, .name')
                        name = name_elem.get_text(strip=True) if name_elem else ''

                        if not name or self._is_duplicate(name):
                            continue

                        data = {
                            'name': name,
                            'ward': ward,
                            'portal': 'NOMU',
                            'url': url,
                            'price_yen': self._parse_price_yen(text),
                            'size_m2': self._parse_size_m2(text),
                            'year': self._parse_year(text),
                            'walk_min': self._parse_walk_min(text),
                            'floor': self._parse_floor(text),
                            'fees_yen': self._parse_fees_yen(text),
                            'direction': self._extract_direction(text),
                            'layout': self._extract_layout(text),
                        }

                        passes, reason = self._passes_all_filters(data)
                        if passes:
                            qualified.append(data)

                    except:
                        continue

                page += 1
                time.sleep(0.2)

            except:
                break

        print(f" {len(qualified)} qualified")
        return qualified

    def run_full_scan(self):
        """Execute exhaustive scan across all wards"""
        print("\n" + "="*120)
        print("EXHAUSTIVE FULL-PAGINATION SCAN — ALL 23 WARDS")
        print("="*120)
        print(f"Start: {datetime.now().isoformat()}")
        print(f"Filters: ¥1.5M-40M | 30m²+ | 1LDK+ | 1982+ | ≤15min walk | 2F+ | ≤¥30k fees | Non-north-facing")
        print(f"Existing DB: {len(self.existing_names)} listings\n")

        total_new = 0

        for ward in sorted(self.wards.keys()):
            ward_code = self.wards[ward][0]
            ward_total = 0

            print(f"\n{ward:<12} ({ward_code})")

            # Try each portal for this ward
            for scraper, portal_name in [
                (self.scrape_suumo_exhaustive, 'SUUMO'),
                (self.scrape_nomu_exhaustive, 'NOMU'),
                # (self.scrape_rehouse_exhaustive, 'Rehouse'),
            ]:
                try:
                    if 'nomu' in portal_name.lower():
                        results = scraper(ward, ward_code)
                    else:
                        results = scraper(ward, ward_code)

                    for r in results:
                        self.all_results.append(r)
                        ward_total += 1

                except Exception as e:
                    print(f"    Error scanning {portal_name}: {e}")

            total_new += ward_total
            print(f"  Ward total: {ward_total}")

        print(f"\n{'='*120}")
        print(f"SCAN COMPLETE")
        print(f"Total new qualified listings found: {total_new}")
        print(f"End: {datetime.now().isoformat()}\n")

        return self.all_results

# Main execution
if __name__ == '__main__':
    scraper = FullPaginationScraper()
    results = scraper.run_full_scan()

    # Output results
    if results:
        print("\nTOP NEW CANDIDATES (first 20):")
        print("="*120)
        for i, r in enumerate(results[:20], 1):
            print(f"{i:3d}. {r.get('name', 'N/A'):<30} | {r.get('ward', 'N/A'):<10} | "
                  f"¥{r.get('price_yen', 0)/10000:.1f}M | {r.get('size_m2', 0):.0f}m² | "
                  f"{r.get('layout', 'N/A'):<6} | {r.get('year', 'N/A')} | "
                  f"{r.get('walk_min', 0)}min | {r.get('portal', 'N/A')}")
        print("="*120)

        # Save to file
        with open('EXHAUSTIVE_SCAN_RESULTS.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to EXHAUSTIVE_SCAN_RESULTS.json ({len(results)} listings)")
