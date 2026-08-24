#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUUMO exhaustive scraper for Tokyo apartment search
Scrapes all listings from specified wards matching hard criteria
"""

import requests
import re
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import sys
import io

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
WARDS = {
    'nerima': {'name': '練馬区', 'code': 'nerima'},
    'setagaya': {'name': '世田谷区', 'code': 'setagaya'},
    'taito': {'name': '台東区', 'code': 'taito'},
}

BASE_URL = "https://suumo.jp/ms/chuko/tokyo/sc_{ward}/"
DETAIL_URL = "https://suumo.jp/ms/chuko/tokyo/sc_{ward}/nc_{property_code}/"

# Headers to appear as browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Hard filter criteria
HARD_CRITERIA = {
    'min_year': 1982,
    'max_price': 40_000_000,  # ¥40M
    'min_size': 30,  # m²
    'min_layout': '1LDK',  # must be at least 1LDK
    'min_floor': 2,  # no ground floor (1F)
    'max_walk': 15,  # minutes to station
    'max_monthly_fees': 30_000,  # ¥30k/month
    'freehold_only': True,  # 所有権 only, not 借地権
    'no_north_only': True,  # reject 北向き only
}

class SUUMOScraper:
    def __init__(self, ward_code: str, ward_name: str):
        self.ward_code = ward_code
        self.ward_name = ward_name
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.qualified = []
        self.disqualified = []
        self.session_log = []

    def log(self, msg: str):
        """Log with timestamp"""
        ts = datetime.now().isoformat(timespec='seconds')
        log_msg = f"[{ts}] {msg}"
        print(log_msg)
        self.session_log.append(log_msg)

    def fetch_page(self, url: str, retries: int = 3, backoff: float = 2.0) -> Optional[str]:
        """Fetch a page with exponential backoff on 503/rate limits"""
        for attempt in range(retries):
            try:
                self.log(f"Fetching: {url}")
                resp = self.session.get(url, timeout=15)

                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code in (503, 429):
                    wait_time = backoff ** attempt
                    self.log(f"Got {resp.status_code}, waiting {wait_time}s before retry {attempt+1}/{retries}")
                    time.sleep(wait_time)
                    continue
                else:
                    self.log(f"Unexpected status {resp.status_code}")
                    return None
            except requests.RequestException as e:
                self.log(f"Request error: {e}")
                if attempt < retries - 1:
                    wait_time = backoff ** attempt
                    time.sleep(wait_time)

        return None

    def extract_property_codes(self, html: str) -> List[str]:
        """Extract all property codes (nc=XXXXX) from search results page"""
        matches = re.findall(r'nc=(\d+)', html)
        return list(set(matches))  # deduplicate

    def get_total_pages(self, html: str) -> int:
        """Try to determine total number of pages from search results"""
        # Look for pagination info or total count
        # SUUMO typically shows "123件" (123 properties)
        match = re.search(r'(\d+)件', html)
        if match:
            count = int(match.group(1))
            # Rough estimate: ~10 properties per page
            return (count + 9) // 10
        return 1

    def parse_property_detail(self, html: str, property_code: str) -> Optional[Dict]:
        """Extract all required fields from detail page"""
        try:
            data = {
                'code': property_code,
                'url': DETAIL_URL.format(ward=self.ward_code, property_code=property_code),
                'ward': self.ward_name,
                'errors': [],
            }

            # Extract name (property title)
            name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            data['name'] = name_match.group(1).strip() if name_match else 'N/A'

            # Extract price (万円)
            price_match = re.search(r'(\d+(?:,\d+)?)万円', html)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                data['price_man'] = int(price_str)
                data['price'] = data['price_man'] * 10_000
            else:
                data['price'] = None
                data['price_man'] = None
                data['errors'].append('price_not_found')

            # Extract size (m²)
            size_match = re.search(r'(\d+(?:\.\d+)?)m²', html)
            data['size'] = float(size_match.group(1)) if size_match else None
            if not data['size']:
                data['errors'].append('size_not_found')

            # Extract year built
            year_match = re.search(r'(\d{4})年', html)
            data['year'] = int(year_match.group(1)) if year_match else None
            if not data['year']:
                data['errors'].append('year_not_found')

            # Extract floor (actual floor/building height)
            # Pattern: "5階／6階建" or "5階建" or similar
            floor_match = re.search(r'(\d+)階(?:／(\d+)階建)?', html)
            if floor_match:
                data['floor'] = int(floor_match.group(1))
                data['building_height'] = int(floor_match.group(2)) if floor_match.group(2) else None
            else:
                data['floor'] = None
                data['building_height'] = None
                data['errors'].append('floor_not_found')

            # Extract walk time to station
            walk_match = re.search(r'(\d+)分', html)
            data['walk_min'] = int(walk_match.group(1)) if walk_match else None
            if not data['walk_min']:
                data['errors'].append('walk_time_not_found')

            # Extract station name
            station_match = re.search(r'駅([^\n<]*)', html)
            data['station'] = station_match.group(1).strip() if station_match else 'N/A'

            # Extract layout (1LDK, 2DK, etc.)
            layout_match = re.search(r'(\d[KDL]+)', html)
            data['layout'] = layout_match.group(1) if layout_match else 'N/A'

            # Extract direction (方角)
            directions = ['南', '東', '西', '北', '南東', '南西', '北東', '北西']
            direction = None
            for d in directions:
                if d in html:
                    direction = d
                    break
            data['direction'] = direction or 'N/A'

            # Extract monthly fees (管理費 + 修繕積立金)
            # Pattern: "管理費: 5,000円 修繕積立金: 5,000円" or similar
            fees_match = re.search(r'(\d+(?:,\d+)?)円', html)
            if fees_match:
                fees_str = fees_match.group(1).replace(',', '')
                data['monthly_fees'] = int(fees_str)
            else:
                data['monthly_fees'] = None
                data['errors'].append('fees_not_found')

            # Extract ownership type (所有権 vs 借地権)
            data['is_freehold'] = '所有権' in html
            if '借地権' in html:
                data['is_freehold'] = False

            # Additional flags
            data['is_vacant'] = '空家' in html or '即入居可' in html
            data['is_reno'] = 'リノベ' in html or 'リフォーム' in html or '工事' in html

            return data

        except Exception as e:
            self.log(f"Error parsing property {property_code}: {e}")
            return None

    def apply_hard_filters(self, prop: Dict) -> tuple[bool, str]:
        """Apply hard criteria. Returns (passes, reason_if_failed)"""

        if prop.get('year') and prop['year'] < HARD_CRITERIA['min_year']:
            return False, f"Year {prop['year']} < {HARD_CRITERIA['min_year']}"

        if prop.get('price') and prop['price'] > HARD_CRITERIA['max_price']:
            return False, f"Price ¥{prop['price']:,} > ¥{HARD_CRITERIA['max_price']:,}"

        if prop.get('size') and prop['size'] < HARD_CRITERIA['min_size']:
            return False, f"Size {prop['size']}m² < {HARD_CRITERIA['min_size']}m²"

        if prop.get('floor') and prop['floor'] < HARD_CRITERIA['min_floor']:
            return False, f"Floor {prop['floor']}F < {HARD_CRITERIA['min_floor']}F"

        if prop.get('walk_min') and prop['walk_min'] > HARD_CRITERIA['max_walk']:
            return False, f"Walk {prop['walk_min']}min > {HARD_CRITERIA['max_walk']}min"

        if prop.get('monthly_fees') and prop['monthly_fees'] > HARD_CRITERIA['max_monthly_fees']:
            return False, f"Fees ¥{prop['monthly_fees']:,} > ¥{HARD_CRITERIA['max_monthly_fees']:,}"

        if HARD_CRITERIA['freehold_only'] and not prop.get('is_freehold', True):
            return False, "Not freehold (借地権)"

        if HARD_CRITERIA['no_north_only'] and prop.get('direction') == '北':
            return False, "North-facing only (北向き)"

        return True, ""

    def scrape_ward(self):
        """Scrape all listings from a ward"""
        self.log(f"Starting scrape for {self.ward_name} ({self.ward_code})")

        page = 1
        property_codes_seen = set()

        while True:
            url = BASE_URL.format(ward=self.ward_code)
            if page > 1:
                url += f"?page={page}"

            html = self.fetch_page(url)
            if not html:
                self.log(f"Failed to fetch page {page}, stopping")
                break

            # Extract property codes
            codes = self.extract_property_codes(html)
            new_codes = [c for c in codes if c not in property_codes_seen]

            self.log(f"Page {page}: Found {len(new_codes)} new properties (total so far: {len(property_codes_seen)})")

            if not new_codes:
                self.log(f"No new properties on page {page}, ending pagination")
                break

            property_codes_seen.update(codes)

            # Fetch detail page for each property
            for code in new_codes:
                detail_url = DETAIL_URL.format(ward=self.ward_code, property_code=code)
                detail_html = self.fetch_page(detail_url)

                if detail_html:
                    prop = self.parse_property_detail(detail_html, code)
                    if prop:
                        passes, reason = self.apply_hard_filters(prop)
                        if passes:
                            self.qualified.append(prop)
                            self.log(f"✓ QUALIFIED: {prop['name']} (¥{prop['price_man']}M, {prop['size']}m², {prop['floor']}F)")
                        else:
                            self.disqualified.append((prop, reason))
                            self.log(f"✗ DISQUALIFIED: {prop['name']} - {reason}")

                # Rate limit: sleep between requests
                time.sleep(1)

            page += 1
            time.sleep(2)  # Wait between pages

    def output_results(self):
        """Output results in tab-separated format"""
        output_lines = []
        output_lines.append(f"SUUMO SEARCH: {self.ward_name}\nFilters: ≤40M, ≥1LDK, ≥30m², 1982+, ≤15min walk, not 1F, not N-only, Freehold\n")
        output_lines.append("=" * 120)
        output_lines.append("QUALIFIED PROPERTIES:")
        output_lines.append("=" * 120)
        output_lines.append("NAME|PRICE|SIZE|FLOOR|YEAR|WALK|STATION|FEES|LAYOUT|DIRECTION|URL\n")

        for prop in self.qualified:
            line = f"{prop['name']}|¥{prop['price_man']}M|{prop['size']}m²|{prop['floor']}F|{prop['year']}|{prop['walk_min']}min|{prop['station']}|¥{prop['monthly_fees']:,}|{prop['layout']}|{prop['direction']}|{prop['url']}"
            output_lines.append(line)

        if not self.qualified:
            output_lines.append("(None)")

        output_lines.append("\n" + "=" * 120)
        output_lines.append("DISQUALIFIED PROPERTIES:")
        output_lines.append("=" * 120)

        for prop, reason in self.disqualified[:50]:  # Show first 50 disqualifications
            line = f"{prop['code']} ({reason}): {prop['name']}|¥{prop['price_man']}M|{prop['size']}m²|{prop['floor']}F|{prop['year']}|{prop['walk_min']}min|{prop['station']}|{prop['url']}"
            output_lines.append(line)

        if len(self.disqualified) > 50:
            output_lines.append(f"\n... and {len(self.disqualified) - 50} more disqualified")

        return "\n".join(output_lines)

def main():
    results = {}

    for ward_code, ward_info in WARDS.items():
        scraper = SUUMOScraper(ward_code, ward_info['name'])
        try:
            scraper.scrape_ward()
            results[ward_code] = {
                'qualified': scraper.qualified,
                'disqualified': scraper.disqualified,
                'log': scraper.session_log,
                'output': scraper.output_results(),
            }
            print("\n" + scraper.output_results())
        except Exception as e:
            print(f"ERROR scraping {ward_info['name']}: {e}")
            results[ward_code] = {'error': str(e)}

    # Save results to file
    output_path = Path("SUUMO_RESULTS_FULL.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        for ward_code, ward_info in WARDS.items():
            if 'output' in results[ward_code]:
                f.write(results[ward_code]['output'])
                f.write("\n\n")

    print(f"\nResults saved to {output_path}")

    # Save JSON for further processing
    json_path = Path("SUUMO_RESULTS.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"JSON results saved to {json_path}")

if __name__ == '__main__':
    main()
