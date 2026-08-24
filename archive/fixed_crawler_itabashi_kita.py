#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fixed SUUMO crawler for Itabashi & Kita with corrections for:
1. Pagination parameter (pn= not page=)
2. Better regex patterns for year/floor/fees
3. Proper handling of parse failures in hard criteria
"""

import requests
import re
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import sys
import io

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

WARDS = {
    'itabashi': '板橋区',
    'kita': '北区',
}

BASE_URL = "https://suumo.jp/ms/chuko/tokyo/sc_{ward}/"
DETAIL_URL = "https://suumo.jp/ms/chuko/tokyo/sc_{ward}/nc_{code}/"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en;q=0.9',
    'Connection': 'keep-alive',
}

class Logger:
    def __init__(self, filename: str):
        self.entries = []
        self.filename = filename

    def log(self, msg: str):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{ts}] {msg}"
        print(line)
        self.entries.append(line)

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.entries))

class FixedCrawler:
    def __init__(self, ward_code: str, ward_name: str, logger: Logger):
        self.ward_code = ward_code
        self.ward_name = ward_name
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.qualified = []
        self.disqualified = []
        self.codes_seen = set()

    def fetch(self, url: str, retries: int = 3) -> Optional[str]:
        """Fetch with rate-limit handling"""
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code in (429, 503):
                    wait = 5 * (2 ** attempt)
                    self.logger.log(f"  HTTP {resp.status_code}, waiting {wait}s ({attempt+1}/{retries})")
                    time.sleep(wait)
                    continue
                else:
                    self.logger.log(f"  HTTP {resp.status_code}")
                    return None
            except requests.RequestException as e:
                self.logger.log(f"  Error: {e}")
                if attempt < retries - 1:
                    time.sleep(5)
        return None

    def extract_codes(self, html: str) -> List[str]:
        """Extract property codes from listing page"""
        return list(set(re.findall(r'nc=(\d+)', html)))

    def extract_year(self, html: str) -> Optional[int]:
        """Extract year from detail page (築年月: YYYY年MM月 format)"""
        # Look for "築年月" pattern specifically
        match = re.search(r'築年月.*?(\d{4})年', html, re.DOTALL)
        if match:
            return int(match.group(1))
        # Fallback: first 4-digit年 (may pick up wrong year if 築年月 not found)
        match = re.search(r'(\d{4})年', html)
        return int(match.group(1)) if match else None

    def extract_floor(self, html: str) -> Optional[Tuple[int, Optional[int]]]:
        """Extract floor (current and building height)
        Returns (current_floor, building_height) or None if not found
        """
        # Pattern: "5階／6階建" or "5階"
        match = re.search(r'(?:^|\s)(\d+)階(?:／(\d+)階建)?', html, re.MULTILINE)
        if match:
            return (int(match.group(1)), int(match.group(2)) if match.group(2) else None)
        return None

    def extract_fees(self, html: str) -> Optional[int]:
        """Extract total monthly fees (管理費 + 修繕積立金)"""
        # Pattern 1: "管理費: 5,000円 修繕積立金: 3,000円" → sum
        mgmt = re.search(r'管理費[:\s]*(\d+(?:,\d+)?)円', html)
        reserve = re.search(r'修繕積立金[:\s]*(\d+(?:,\d+)?)円', html)

        if mgmt and reserve:
            mgmt_val = int(mgmt.group(1).replace(',', ''))
            reserve_val = int(reserve.group(1).replace(',', ''))
            return mgmt_val + reserve_val

        # Pattern 2: Single "共益費" or "管理費: 8,000円" (total)
        if mgmt:
            return int(mgmt.group(1).replace(',', ''))

        return None

    def parse_detail(self, html: str, code: str) -> Optional[Dict]:
        """Parse detail page with fixed patterns

        Returns Dict if 1982+ and all critical fields found, None otherwise
        """
        # CRITICAL: Check year first before anything else
        year = self.extract_year(html)
        if not year:
            self.logger.log(f"    └─ Year: MISSING, skip")
            return None
        if year < 1982:
            self.logger.log(f"    └─ Year: {year} (pre-1982), skip")
            return None

        # Year passes - now extract all other fields
        data = {
            'code': code,
            'url': DETAIL_URL.format(ward=self.ward_code, code=code),
            'year': year,
        }

        # Name
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        data['name'] = name_match.group(1).strip() if name_match else 'N/A'

        # Price (万円)
        price_match = re.search(r'(\d+(?:,\d+)?)万円', html)
        if price_match:
            data['price_man'] = int(price_match.group(1).replace(',', ''))
            data['price'] = data['price_man'] * 10_000
        else:
            data['price_man'] = None
            data['price'] = None

        # Size (m²)
        size_match = re.search(r'(\d+(?:\.\d+)?)m²', html)
        data['size'] = float(size_match.group(1)) if size_match else None

        # Floor
        floor_info = self.extract_floor(html)
        if floor_info:
            data['floor'] = floor_info[0]
            data['building_height'] = floor_info[1]
        else:
            data['floor'] = None
            data['building_height'] = None

        # Walk time (分)
        walk_match = re.search(r'(\d+)分(?!以上)', html)
        data['walk_min'] = int(walk_match.group(1)) if walk_match else None

        # Station
        station_match = re.search(r'([^\s<>]+駅)', html)
        data['station'] = station_match.group(1).strip() if station_match else 'N/A'

        # Layout
        layout_match = re.search(r'(\d[KDL]+)', html)
        data['layout'] = layout_match.group(1) if layout_match else 'N/A'

        # Direction (方角)
        directions = ['南東', '南西', '北東', '北西', '南', '東', '西', '北']
        direction = None
        for d in directions:
            if d in html:
                direction = d
                break
        data['direction'] = direction or 'N/A'

        # Fees (fixed extraction)
        data['monthly_fees'] = self.extract_fees(html)

        # Ownership
        data['is_freehold'] = '所有権' in html and '借地権' not in html

        # Flags
        data['is_vacant'] = '空家' in html or '即入居可' in html
        data['is_reno'] = any(x in html for x in ['リノベ', 'リフォーム', '工事', '改修'])

        return data

    def check_criteria(self, prop: Dict) -> Tuple[bool, str]:
        """Check hard criteria. FAIL on missing critical fields."""

        # Missing critical fields = automatic FAIL
        if prop.get('price') is None:
            return False, "Price missing"
        if prop.get('size') is None:
            return False, "Size missing"
        if prop.get('floor') is None:
            return False, "Floor missing"
        if prop.get('walk_min') is None:
            return False, "Walk time missing"
        if prop.get('monthly_fees') is None:
            return False, "Fees missing"

        # Hard criteria
        if prop['price'] > 40_000_000:
            return False, f"Price {prop['price_man']}M > 40M"
        if prop['size'] < 30:
            return False, f"Size {prop['size']}m² < 30m²"
        if prop['floor'] < 2:
            return False, f"Floor {prop['floor']}F < 2F"
        if prop['walk_min'] > 15:
            return False, f"Walk {prop['walk_min']}min > 15min"
        if prop['monthly_fees'] > 30_000:
            return False, f"Fees {prop['monthly_fees']}yen > 30k"
        if not prop['is_freehold']:
            return False, "Not freehold"
        if prop['direction'] == '北':
            return False, "North-only"

        return True, ""

    def crawl(self):
        """Main crawl logic"""
        self.logger.log(f"\n{'='*70}")
        self.logger.log(f"CRAWLING: {self.ward_name}")
        self.logger.log(f"{'='*70}")

        page = 1
        while True:
            # USE pn= PARAMETER (not page=)
            url = BASE_URL.format(ward=self.ward_code)
            if page > 1:
                url += f"?pn={page}"

            self.logger.log(f"Fetching listing page {page}: {url}")
            html = self.fetch(url)
            if not html:
                self.logger.log(f"Failed, stopping")
                break

            codes = self.extract_codes(html)
            new_codes = [c for c in codes if c not in self.codes_seen]

            self.logger.log(f"  Found {len(new_codes)} new properties")

            if not new_codes:
                self.logger.log(f"No new properties, pagination complete")
                break

            self.codes_seen.update(codes)

            # Detail-fetch each property
            for code in new_codes:
                url = DETAIL_URL.format(ward=self.ward_code, code=code)
                self.logger.log(f"  Detail fetch: {code}")

                html = self.fetch(url)
                if not html:
                    self.logger.log(f"    └─ Fetch failed")
                    time.sleep(5)
                    continue

                prop = self.parse_detail(html, code)
                if not prop:
                    # Already logged in parse_detail
                    time.sleep(5)
                    continue

                passes, reason = self.check_criteria(prop)
                if passes:
                    self.qualified.append(prop)
                    self.logger.log(f"    └─ PASS: {prop['name']} - {prop['price_man']}M, {prop['size']}m², {prop['floor']}F")
                else:
                    self.disqualified.append((prop, reason))
                    self.logger.log(f"    └─ FAIL: {prop['name']} - {reason}")

                # AGGRESSIVE 5s sleep between details
                time.sleep(5)

            # 5s sleep before next page
            self.logger.log(f"Sleeping 5s before next page...")
            time.sleep(5)
            page += 1

        self.logger.log(f"\n{self.ward_name} Summary:")
        self.logger.log(f"  Qualified: {len(self.qualified)}")
        self.logger.log(f"  Disqualified: {len(self.disqualified)}\n")

def main():
    logger = Logger("fixed_crawler.log")
    crawlers = {}

    for ward_code, ward_name in WARDS.items():
        crawler = FixedCrawler(ward_code, ward_name, logger)
        try:
            crawler.crawl()
            crawlers[ward_code] = crawler
        except Exception as e:
            logger.log(f"ERROR: {e}")
            import traceback
            logger.log(traceback.format_exc())

    # Output results
    lines = [
        "FIXED CRAWLER: Itabashi & Kita (1982+)",
        "Filters: ≤40M, ≥1LDK, ≥30m², 1982+, ≤15min walk, 2F+, not N-only, Freehold",
        "",
        "=" * 150,
        "QUALIFIED",
        "=" * 150,
        "WARD|NAME|PRICE|SIZE|FLOOR|YEAR|WALK|STATION|FEES|LAYOUT|DIRECTION|URL",
    ]

    all_qualified = []
    for crawler in crawlers.values():
        all_qualified.extend(crawler.qualified)

    for prop in sorted(all_qualified, key=lambda x: x.get('price') or 0):
        line = f"{prop.get('ward', 'N/A')}|{prop['name']}|{prop['price_man']}M|{prop['size']}m²|{prop['floor']}F|{prop['year']}|{prop['walk_min']}min|{prop['station']}|{prop['monthly_fees']}yen|{prop['layout']}|{prop['direction']}|{prop['url']}"
        lines.append(line)

    if not all_qualified:
        lines.append("(None)")

    lines.append("")
    lines.append("=" * 150)
    lines.append("DISQUALIFIED (first 50)")
    lines.append("=" * 150)

    all_disq = []
    for crawler in crawlers.values():
        all_disq.extend(crawler.disqualified)

    for prop, reason in all_disq[:50]:
        line = f"{prop.get('ward', 'N/A')}|{prop['name']}|{prop['price_man']}M|{prop['size']}m²|{prop['floor']}F|{prop['year']}|{reason}"
        lines.append(line)

    output = "\n".join(lines)
    print("\n" + output)

    # Save
    with open("FIXED_RESULTS.txt", 'w', encoding='utf-8') as f:
        f.write(output)

    json_out = {}
    for code, crawler in crawlers.items():
        json_out[code] = {
            'qualified': crawler.qualified,
            'disqualified': [(p[0], p[1]) for p in crawler.disqualified],
        }

    with open("FIXED_RESULTS.json", 'w', encoding='utf-8') as f:
        json.dump(json_out, f, ensure_ascii=False, indent=2, default=str)

    logger.save()
    logger.log(f"Done. Results in FIXED_RESULTS.txt / FIXED_RESULTS.json")

if __name__ == '__main__':
    main()
