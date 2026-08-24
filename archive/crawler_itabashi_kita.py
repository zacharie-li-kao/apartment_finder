#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exhaustive paced SUUMO crawler for Itabashi & Kita
Uses 5-second sleep between ALL requests (aggressive pacing for rate limit avoidance)
Focuses on 1982+ properties only to reduce request count
"""

import requests
import re
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional
import sys
import io

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
WARDS = {
    'itabashi': '板橋区',
    'kita': '北区',
}

BASE_URL = "https://suumo.jp/ms/chuko/tokyo/sc_{ward}/"
DETAIL_URL = "https://suumo.jp/ms/chuko/tokyo/sc_{ward}/nc_{code}/"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

# Hard criteria
HARD_CRITERIA = {
    'min_year': 1982,
    'max_price': 40_000_000,
    'min_size': 30,
    'min_floor': 2,
    'max_walk': 15,
    'max_monthly_fees': 30_000,
}

class CrawlerLog:
    def __init__(self, filename: str):
        self.filename = filename
        self.entries = []

    def log(self, msg: str):
        ts = datetime.now().isoformat(timespec='seconds')
        log_msg = f"[{ts}] {msg}"
        print(log_msg)
        self.entries.append(log_msg)

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.entries))

class ITKCrawler:
    def __init__(self, ward_code: str, ward_name: str, logger: CrawlerLog):
        self.ward_code = ward_code
        self.ward_name = ward_name
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.qualified = []
        self.disqualified = []
        self.property_codes = set()

    def fetch_page(self, url: str, page_num: int = None, retries: int = 3) -> Optional[str]:
        """Fetch page with aggressive rate limiting"""
        desc = f"page {page_num}" if page_num else "detail"
        for attempt in range(retries):
            try:
                self.logger.log(f"Fetching {desc}: {url}")
                resp = self.session.get(url, timeout=15)

                if resp.status_code == 200:
                    self.logger.log(f"✓ Got 200 OK")
                    return resp.text
                elif resp.status_code in (429, 503):
                    wait = 5 * (2 ** attempt)
                    self.logger.log(f"⚠ HTTP {resp.status_code}. Waiting {wait}s (attempt {attempt+1}/{retries})")
                    time.sleep(wait)
                    continue
                else:
                    self.logger.log(f"✗ HTTP {resp.status_code}")
                    return None
            except requests.RequestException as e:
                self.logger.log(f"✗ Request error: {e}")
                if attempt < retries - 1:
                    time.sleep(5)

        return None

    def extract_codes(self, html: str) -> List[str]:
        """Extract property codes from listing page"""
        matches = re.findall(r'nc=(\d+)', html)
        return list(set(matches))

    def parse_detail(self, html: str, code: str) -> Optional[Dict]:
        """Parse detail page. Return None if pre-1982 or missing year."""
        try:
            # Extract year first - if pre-1982, skip entire parse
            year_match = re.search(r'(\d{4})年', html)
            if not year_match:
                self.logger.log(f"  └─ Year not found, skipping")
                return None

            year = int(year_match.group(1))
            if year < HARD_CRITERIA['min_year']:
                self.logger.log(f"  └─ Year {year} < 1982, skipping")
                return None

            data = {
                'code': code,
                'url': DETAIL_URL.format(ward=self.ward_code, code=code),
                'ward': self.ward_name,
            }

            # Name
            name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            data['name'] = name_match.group(1).strip() if name_match else 'N/A'

            # Price (万円)
            price_match = re.search(r'(\d+(?:,\d+)?)万円', html)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                data['price_man'] = int(price_str)
                data['price'] = data['price_man'] * 10_000
            else:
                data['price'] = None
                data['price_man'] = None

            # Size
            size_match = re.search(r'(\d+(?:\.\d+)?)m²', html)
            data['size'] = float(size_match.group(1)) if size_match else None

            # Year (already extracted)
            data['year'] = year

            # Floor
            floor_match = re.search(r'(\d+)階(?:／(\d+)階建)?', html)
            if floor_match:
                data['floor'] = int(floor_match.group(1))
                data['building_height'] = int(floor_match.group(2)) if floor_match.group(2) else None
            else:
                data['floor'] = None

            # Walk time
            walk_match = re.search(r'(\d+)分', html)
            data['walk_min'] = int(walk_match.group(1)) if walk_match else None

            # Station
            station_match = re.search(r'([^\n<]*?駅)', html)
            data['station'] = station_match.group(1).strip() if station_match else 'N/A'

            # Layout
            layout_match = re.search(r'(\d[KDL]+)', html)
            data['layout'] = layout_match.group(1) if layout_match else 'N/A'

            # Direction
            directions = ['南東', '南西', '北東', '北西', '南', '東', '西', '北']
            direction = None
            for d in directions:
                if d in html:
                    direction = d
                    break
            data['direction'] = direction or 'N/A'

            # Monthly fees
            fees_match = re.search(r'(\d+(?:,\d+)?)円', html)
            if fees_match:
                data['monthly_fees'] = int(fees_match.group(1).replace(',', ''))
            else:
                data['monthly_fees'] = None

            # Ownership
            data['is_freehold'] = '所有権' in html and '借地権' not in html

            # Flags
            data['is_vacant'] = '空家' in html or '即入居可' in html
            data['is_reno'] = any(x in html for x in ['リノベ', 'リフォーム', '工事'])

            return data

        except Exception as e:
            self.logger.log(f"  └─ Parse error: {e}")
            return None

    def check_hard_criteria(self, prop: Dict) -> tuple[bool, str]:
        """Check if property passes hard filters"""

        if prop.get('year') and prop['year'] < HARD_CRITERIA['min_year']:
            return False, f"Year {prop['year']}"

        if prop.get('price') and prop['price'] > HARD_CRITERIA['max_price']:
            return False, f"Price ¥{prop['price']:,} > ¥40M"

        if prop.get('size') and prop['size'] < HARD_CRITERIA['min_size']:
            return False, f"Size {prop['size']}m²"

        if prop.get('floor') and prop['floor'] < HARD_CRITERIA['min_floor']:
            return False, f"Floor {prop['floor']}F"

        if prop.get('walk_min') and prop['walk_min'] > HARD_CRITERIA['max_walk']:
            return False, f"Walk {prop['walk_min']}min"

        if prop.get('monthly_fees') and prop['monthly_fees'] > HARD_CRITERIA['max_monthly_fees']:
            return False, f"Fees ¥{prop['monthly_fees']:,}"

        if not prop.get('is_freehold'):
            return False, "Not freehold"

        if prop.get('direction') == '北':
            return False, "North-only"

        return True, ""

    def crawl_ward(self):
        """Crawl all pages and detail-fetch 1982+ properties"""
        self.logger.log(f"\n{'='*60}")
        self.logger.log(f"STARTING: {self.ward_name} ({self.ward_code})")
        self.logger.log(f"{'='*60}")

        page = 1
        total_codes = 0

        # Pagination loop
        while True:
            url = BASE_URL.format(ward=self.ward_code)
            if page > 1:
                url += f"?page={page}"

            html = self.fetch_page(url, page_num=page)
            if not html:
                self.logger.log(f"Failed to fetch page {page}, stopping")
                break

            codes = self.extract_codes(html)
            new_codes = [c for c in codes if c not in self.property_codes]

            self.logger.log(f"Page {page}: {len(new_codes)} new properties (total unique so far: {total_codes + len(new_codes)})")

            if not new_codes:
                self.logger.log(f"No new properties on page {page}, pagination complete")
                break

            self.property_codes.update(codes)
            total_codes += len(new_codes)

            # AGGRESSIVE SLEEP before moving to next page
            self.logger.log(f"Waiting 5s before next page...")
            time.sleep(5)

            page += 1

        self.logger.log(f"\n{'='*60}")
        self.logger.log(f"DETAIL-FETCHING: {len(self.property_codes)} unique properties (1982+ only)")
        self.logger.log(f"{'='*60}")

        # Detail-fetch loop
        processed = 0
        for code in sorted(self.property_codes):
            processed += 1
            url = DETAIL_URL.format(ward=self.ward_code, code=code)

            html = self.fetch_page(url)
            if not html:
                self.logger.log(f"[{processed}/{len(self.property_codes)}] Code {code}: fetch failed")
                # Still sleep for rate limit consistency
                time.sleep(5)
                continue

            prop = self.parse_detail(html, code)
            if prop is None:
                # Already logged in parse_detail
                time.sleep(5)
                continue

            # Check hard criteria
            passes, reason = self.check_hard_criteria(prop)
            if passes:
                self.qualified.append(prop)
                self.logger.log(f"[{processed}/{len(self.property_codes)}] ✓ {prop['name']} - ¥{prop['price_man']}M, {prop['size']}m², {prop['floor']}F, {prop['walk_min']}min walk")
            else:
                self.disqualified.append((prop, reason))
                self.logger.log(f"[{processed}/{len(self.property_codes)}] ✗ {prop['name']} - {reason}")

            # AGGRESSIVE SLEEP between detail requests
            self.logger.log(f"Waiting 5s...")
            time.sleep(5)

        self.logger.log(f"\n{'='*60}")
        self.logger.log(f"RESULTS: {self.ward_name}")
        self.logger.log(f"  Qualified: {len(self.qualified)}")
        self.logger.log(f"  Disqualified: {len(self.disqualified)}")
        self.logger.log(f"{'='*60}\n")

def format_output(crawlers: Dict[str, ITKCrawler]) -> str:
    """Format results as TSV"""
    lines = []
    lines.append("SUUMO EXHAUSTIVE SEARCH: Itabashi-ku & Kita-ku (1982+)")
    lines.append("Filters: ≤40M, ≥1LDK, ≥30m², 1982+, ≤15min walk, 2F+, not N-only, Freehold\n")

    all_qualified = []
    for crawler in crawlers.values():
        all_qualified.extend(crawler.qualified)

    lines.append("=" * 140)
    lines.append("QUALIFIED PROPERTIES:")
    lines.append("=" * 140)
    lines.append("WARD|NAME|PRICE|SIZE|FLOOR|YEAR|WALK|STATION|FEES|LAYOUT|DIRECTION|VACANT|RENO|URL")

    for prop in sorted(all_qualified, key=lambda x: x.get('price') or 0):
        line = f"{prop['ward']}|{prop['name']}|¥{prop['price_man']}M|{prop['size']}m²|{prop['floor']}F|{prop['year']}|{prop['walk_min']}min|{prop['station']}|¥{prop.get('monthly_fees', 'N/A'):,}|{prop['layout']}|{prop['direction']}|{prop['is_vacant']}|{prop['is_reno']}|{prop['url']}"
        lines.append(line)

    if not all_qualified:
        lines.append("(None)")

    lines.append(f"\nTotal qualified: {len(all_qualified)}\n")

    return "\n".join(lines)

def main():
    logger = CrawlerLog("itabashi_kita_crawler.log")
    crawlers = {}

    for ward_code, ward_name in WARDS.items():
        crawler = ITKCrawler(ward_code, ward_name, logger)
        try:
            crawler.crawl_ward()
            crawlers[ward_code] = crawler
        except Exception as e:
            logger.log(f"ERROR crawling {ward_name}: {e}")

    # Output results
    output = format_output(crawlers)
    print("\n" + output)

    # Save to file
    output_path = Path("ITABASHI_KITA_RESULTS.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)
    logger.log(f"Results saved to {output_path}")

    # Save JSON
    json_data = {}
    for code, crawler in crawlers.items():
        json_data[code] = {
            'qualified': crawler.qualified,
            'disqualified': [(p[0], p[1]) for p in crawler.disqualified],
        }

    json_path = Path("ITABASHI_KITA_RESULTS.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    logger.log(f"JSON saved to {json_path}")

    # Save log
    logger.save()
    logger.log(f"Log saved to itabashi_kita_crawler.log")

if __name__ == '__main__':
    main()
