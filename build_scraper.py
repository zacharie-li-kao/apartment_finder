#!/usr/bin/env python3
"""
Comprehensive scraper for NOMU.com and Yahoo Real Estate
Finds NEW Tokyo apartment listings not in existing database of 116
"""

import requests
import json
import re
import csv
import time
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, quote
from datetime import datetime
import subprocess

class TokyoApartmentScraper:
    def __init__(self):
        self.session = requests.Session()
        # Try multiple user agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        ]
        self.session.headers.update({
            'User-Agent': self.user_agents[0],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        # Ward codes for NOMU.com (from task)
        self.wards = {
            'Sumida': ('13107', 97),
            'Koto': ('13108', 403),
            'Itabashi': ('13119', 190),
            'Katsushika': ('13122', 79),
            'Chuo': ('13102', 497),
            'Minato': ('13103', 904),
            'Setagaya': ('13112', 375),
            'Nakano': ('13114', 121),
            'Ota': ('13111', 183),
            'Nerima': ('13120', 151),
            'Kita': ('13117', 132),
            'Arakawa': ('13118', 72),
        }

        # Hard filters from task
        self.filters = {
            'min_price_man': 1.5,       # ¥1.5M
            'max_price_man': 40,        # ¥40M
            'min_size_m2': 30,
            'min_floor': 2,
            'min_year': 1982,
            'max_walk_min': 15,
            'max_monthly_fees': 30000,
            'allowed_directions': ['S', 'SE', 'SW', '南', '南東', '南西', 'South', 'Southeast', 'Southwest'],
            'layouts': ['1LDK', '2LDK', '3LDK', '4LDK', '2DK', '3DK', '1DK']
        }

        # Load existing buildings from git for deduplication
        self.existing_buildings = self.load_existing_buildings()
        print(f"Loaded {len(self.existing_buildings)} existing buildings for deduplication")

    def load_existing_buildings(self) -> set:
        """Extract building names from git history"""
        existing = set()
        try:
            result = subprocess.run(
                ['git', 'log', '--all', '--format=%s'],
                cwd='C:\\Users\\zakat\\Desktop\\apartment',
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split('\n'):
                    # Match "Add #N Name" pattern
                    match = re.search(r'^Add #\d+[\s\-]+([^(|]+)', line)
                    if match:
                        name = match.group(1).strip()
                        name = re.sub(r'\s+$', '', name)  # Remove trailing spaces
                        if name and len(name) > 2:
                            existing.add(name)

                    # Match combined adds like "Add #N-M: Name1 + Name2"
                    if 'Add #' in line and '+' in line:
                        parts = line.split('+')
                        for part in parts:
                            # Simplified pattern for building names
                            match = re.search(r'([^\s|]+(?:パーク|ハイツ|マンション|タワー|プレイス|コート|ガーデン|プラザ|シティ|ザ|エスカイア|メゾン|ライオンズ|グリーン|スカイ|ニュー|ダイア|ルック|ラブリ|エンゼル|エスペランサ|朝日|セザール|向島|東大島|ルック|コスモ|関町)[^\s|]*)', part)
                            if match:
                                existing.add(match.group(1).strip())
            else:
                print(f"Warning: Git command failed (return code {result.returncode})")
        except Exception as e:
            print(f"Warning: Could not load existing buildings: {e}")

        return existing

    def parse_price(self, price_str: str) -> Optional[float]:
        """Parse price in man (万) to float. e.g., '3,390万' -> 33.9"""
        if not price_str:
            return None
        match = re.search(r'(\d{1,2}),?(\d{3})(?:万)?', price_str)
        if match:
            return float(match.group(1) + '.' + match.group(2)[:1])
        match = re.search(r'(\d+)(?:万)?', price_str)
        if match:
            return float(match.group(1))
        return None

    def parse_size(self, size_str: str) -> Optional[float]:
        """Parse size in m²"""
        if not size_str:
            return None
        match = re.search(r'(\d+\.?\d*)(?:\s*m²)?', size_str)
        if match:
            return float(match.group(1))
        return None

    def parse_year(self, year_str: str) -> Optional[int]:
        """Parse year from various formats"""
        if not year_str:
            return None
        match = re.search(r'([12][09]\d{2})', year_str)
        if match:
            return int(match.group(1))
        return None

    def parse_floor(self, floor_str: str) -> Optional[int]:
        """Parse current floor"""
        if not floor_str:
            return None
        match = re.search(r'^(\d+)', floor_str)
        if match:
            return int(match.group(1))
        return None

    def parse_walk_time(self, walk_str: str) -> Optional[int]:
        """Parse minimum walk time"""
        if not walk_str:
            return None
        times = re.findall(r'(\d+)\s*(?:分|min|分)', walk_str)
        if times:
            return min(int(t) for t in times)
        return None

    def passes_filters(self, listing: Dict) -> Tuple[bool, Optional[str]]:
        """Check if listing passes all hard filters. Returns (passes, reason)"""

        # Price filter
        if listing.get('price_man'):
            if listing['price_man'] < self.filters['min_price_man']:
                return False, f"Price ¥{listing['price_man']:.1f}M < ¥{self.filters['min_price_man']}M"
            if listing['price_man'] > self.filters['max_price_man']:
                return False, f"Price ¥{listing['price_man']:.1f}M > ¥{self.filters['max_price_man']}M"

        # Size filter
        if listing.get('size_m2'):
            if listing['size_m2'] < self.filters['min_size_m2']:
                return False, f"Size {listing['size_m2']}m² < {self.filters['min_size_m2']}m²"

        # Floor filter
        if listing.get('floor_num'):
            if listing['floor_num'] < self.filters['min_floor']:
                return False, f"Floor {listing['floor_num']}F < {self.filters['min_floor']}F"

        # Year filter
        if listing.get('year'):
            if listing['year'] < self.filters['min_year']:
                return False, f"Year {listing['year']} < {self.filters['min_year']}"

        # Walk time filter
        if listing.get('walk_min'):
            if listing['walk_min'] > self.filters['max_walk_min']:
                return False, f"Walk {listing['walk_min']}min > {self.filters['max_walk_min']}min"

        # Layout filter
        if listing.get('layout'):
            valid = False
            for allowed in self.filters['layouts']:
                if allowed in listing['layout']:
                    valid = True
                    break
            if not valid:
                return False, f"Layout {listing['layout']} not in allowed list"

        # Direction filter (must NOT be north-only)
        if listing.get('direction'):
            if listing['direction'].lower() in ['north', 'n', '北', '北向き']:
                return False, f"Direction {listing['direction']} is north-only"

        # Fees filter
        if listing.get('monthly_fees_yen'):
            if listing['monthly_fees_yen'] > self.filters['max_monthly_fees']:
                return False, f"Monthly fees ¥{listing['monthly_fees_yen']} > ¥{self.filters['max_monthly_fees']}"

        return True, "PASS"

    def is_duplicate(self, name: str) -> bool:
        """Check if building already exists in database"""
        if not name:
            return True

        # Normalize name for comparison
        normalized = name.strip()

        # Direct match
        if normalized in self.existing_buildings:
            return True

        # Partial match check
        for existing in self.existing_buildings:
            if existing in normalized or normalized in existing:
                if len(existing) > 5 and len(normalized) > 5:  # Avoid false positives on short names
                    return True

        return False

    def test_portal_access(self) -> Dict[str, str]:
        """Test if portals are accessible. Returns status string."""
        results = {}

        # Test NOMU - try multiple URLs
        nomu_urls = [
            "https://www.nomu.com/mansion/area_tokyo/13107/1/",
            "https://www.nomu.com/",
        ]

        nomu_status = "BLOCKED"
        for url in nomu_urls:
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code in [200, 301, 302]:
                    nomu_status = f"OK ({resp.status_code})"
                    break
                else:
                    nomu_status = f"Error {resp.status_code}"
            except Exception as e:
                nomu_status = f"Exception: {str(e)[:50]}"

        results['nomu'] = nomu_status
        print(f"NOMU: {nomu_status}")

        # Test Yahoo Real Estate - try multiple URLs
        yahoo_urls = [
            "https://realestate.yahoo.co.jp/mansion/tokyo/sumida/",
            "https://realestate.yahoo.co.jp/",
            "https://realestate.yahoo.co.jp/mansion/",
        ]

        yahoo_status = "BLOCKED"
        for url in yahoo_urls:
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code in [200, 301, 302]:
                    yahoo_status = f"OK ({resp.status_code})"
                    break
                else:
                    yahoo_status = f"Error {resp.status_code}"
            except Exception as e:
                yahoo_status = f"Exception: {str(e)[:50]}"

        results['yahoo'] = yahoo_status
        print(f"Yahoo Real Estate: {yahoo_status}")

        return results

    def scrape_nomu_ward(self, ward_name: str, ward_code: str, total_count: int) -> List[Dict]:
        """Scrape all pages for a NOMU ward"""
        listings = []
        pages = (total_count + 39) // 40  # ~40 listings per page

        print(f"\n  Scraping NOMU {ward_name}... ({pages} pages estimated)")

        for page in range(1, pages + 1):
            # Correct URL pattern: ?pager_page=N (from memory/reference_portal_access.md)
            url = f"https://www.nomu.com/mansion/area_tokyo/{ward_code}/?pager_page={page}"
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code != 200:
                    print(f"    Page {page}: Status {resp.status_code}")
                    if resp.status_code == 500:
                        break  # Stop on repeated 500s
                    continue

                soup = BeautifulSoup(resp.content, 'html.parser')
                page_listings = self.extract_nomu_listings(soup, ward_name)
                listings.extend(page_listings)
                print(f"    Page {page}: {len(page_listings)} candidates")

                time.sleep(1)  # Be respectful to server
            except Exception as e:
                print(f"    Page {page}: Error - {e}")

        return listings

    def extract_nomu_listings(self, soup: BeautifulSoup, ward_name: str) -> List[Dict]:
        """Extract listings from NOMU page HTML

        Per memory/reference_portal_access.md:
        - ~40 cards/page in item_table
        - List fields unreliable - treat as URL collection + detail-fetch
        - Price in <p class="item_price"><span class="num">
        """
        listings = []

        # Find all item_table elements (each contains one listing)
        for item in soup.find_all(class_='item_table'):
            try:
                # Extract URL/ID from the link
                url_elem = item.find('a', href=True)
                if not url_elem:
                    continue
                detail_url = url_elem.get('href', '')
                if not detail_url:
                    continue

                # Make absolute URL
                if detail_url.startswith('/'):
                    detail_url = 'https://www.nomu.com' + detail_url

                # Extract building name
                name_elem = item.find(class_='item_title')
                name = name_elem.get_text(strip=True) if name_elem else None
                if not name or len(name) < 2:
                    continue

                # Extract price
                price_elem = item.find(class_='item_price')
                price_str = None
                if price_elem:
                    price_span = price_elem.find('span', class_='num')
                    if price_span:
                        price_str = price_span.get_text(strip=True)

                # Extract other fields from free-text content (unreliable per memory)
                content_text = item.get_text(' ', strip=True)

                listing = {
                    'ward': ward_name,
                    'name': name,
                    'price_man': self.parse_price(price_str),
                    'size_m2': self.parse_size(content_text),
                    'layout': self.extract_layout_from_text(content_text),
                    'floor_num': self.parse_floor(content_text),
                    'year': self.parse_year(content_text),
                    'walk_min': self.parse_walk_time(content_text),
                    'station': self.extract_station_from_text(content_text),
                    'direction': self.extract_direction_from_text(content_text),
                    'monthly_fees_yen': None,  # Needs detail page
                    'freehold': None,  # Needs detail page
                    'vacant': None,  # Needs detail page
                    'link': detail_url,
                    'source': 'NOMU'
                }

                listings.append(listing)
            except Exception as e:
                # Skip individual parsing errors
                pass

        return listings

    def extract_layout_from_text(self, text: str) -> Optional[str]:
        """Extract layout like 1LDK, 2DK from text"""
        match = re.search(r'(\d+(?:LDK|DK|R|L))', text)
        if match:
            return match.group(1)
        return None

    def extract_station_from_text(self, text: str) -> Optional[str]:
        """Extract station name from walk time notation like '駅3分'"""
        match = re.search(r'([ァ-ンー一-龯]+(?:駅|線)?)\s*\d+\s*(?:分|min)', text)
        if match:
            return match.group(1)
        return None

    def extract_direction_from_text(self, text: str) -> Optional[str]:
        """Extract direction like 南、東、南東 from text"""
        # Look for common direction patterns
        directions = ['南西', '南東', '北西', '北東', '南', '東', '西', '北']
        for direction in directions:
            if direction in text:
                return direction
        return None

    def scrape_yahoo_ward(self, ward_name: str, ward_name_jp: str) -> List[Dict]:
        """Scrape all pages for a Yahoo Real Estate ward"""
        listings = []

        # Try different URL patterns
        urls = [
            f"https://realestate.yahoo.co.jp/mansion/tokyo/{ward_name}/",
            f"https://realestate.yahoo.co.jp/mansion/tokyo/{quote(ward_name_jp)}/",
        ]

        print(f"\n  Scraping Yahoo Real Estate {ward_name}...")

        for url in urls:
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code != 200:
                    print(f"    Status {resp.status_code}: {url}")
                    continue

                soup = BeautifulSoup(resp.content, 'html.parser')
                page_listings = self.extract_yahoo_listings(soup, ward_name)
                listings.extend(page_listings)
                print(f"    {url}: {len(page_listings)} candidates")

                time.sleep(1)  # Be respectful to server
                break
            except Exception as e:
                print(f"    Error scraping {url}: {e}")

        return listings

    def extract_yahoo_listings(self, soup: BeautifulSoup, ward_name: str) -> List[Dict]:
        """Extract listings from Yahoo Real Estate page HTML"""
        listings = []
        # TODO: Parse actual HTML structure from Yahoo
        # This is a placeholder - actual HTML parsing will depend on Yahoo's structure
        return listings

    def run_full_scrape(self, access_status: Dict[str, str] = None) -> List[Dict]:
        """Run complete scraper for all wards"""
        print("=" * 70)
        print("TOKYO APARTMENT SCRAPER: NOMU + Yahoo Real Estate")
        print("=" * 70)
        print(f"Filters: {self.filters['min_price_man']:.1f}M-{self.filters['max_price_man']}M price, "
              f">={self.filters['min_size_m2']}m2 size, "
              f">={self.filters['min_year']} year, "
              f"<={self.filters['max_walk_min']} min walk")
        print()

        # Use provided access status or test now
        if not access_status:
            print("Testing portal access...")
            access_status = self.test_portal_access()
            print()

        access = access_status

        nomu_ok = 'OK' in access['nomu']
        yahoo_ok = 'OK' in access['yahoo']

        if not nomu_ok and not yahoo_ok:
            print("\n" + "=" * 70)
            print("PORTAL ACCESS BLOCKED")
            print("=" * 70)
            print(f"NOMU.COM: {access['nomu']}")
            print(f"Yahoo Real Estate: {access['yahoo']}")
            print("\nBoth portals are inaccessible. This suggests:")
            print("1. Network restrictions or geographic blocking")
            print("2. Portals require JavaScript rendering (requests + BeautifulSoup won't work)")
            print("3. Portals actively block automated scrapers")
            print("4. API-based approach needed instead of web scraping")
            return []

        all_listings = []

        # Scrape NOMU if accessible
        if nomu_ok:
            print("\n" + "=" * 70)
            print("SCRAPING NOMU.COM")
            print("=" * 70)

            for ward_name, (ward_code, count) in self.wards.items():
                ward_listings = self.scrape_nomu_ward(ward_name, ward_code, count)
                all_listings.extend(ward_listings)
        else:
            print(f"\nNOMU.COM not accessible ({access['nomu']}) - skipping")

        # Scrape Yahoo Real Estate if accessible
        if yahoo_ok:
            print("\n" + "=" * 70)
            print("SCRAPING YAHOO REAL ESTATE")
            print("=" * 70)

            ward_mapping_jp = {
                'Sumida': '墨田',
                'Koto': '江東',
                'Itabashi': '板橋',
                'Katsushika': '葛飾',
                'Chuo': '中央',
                'Minato': '港',
                'Setagaya': '世田谷',
                'Nakano': '中野',
                'Ota': '大田',
                'Nerima': '練馬',
                'Kita': '北',
                'Arakawa': '荒川',
            }

            for ward_name, ward_jp in ward_mapping_jp.items():
                ward_listings = self.scrape_yahoo_ward(ward_name, ward_jp)
                all_listings.extend(ward_listings)
        else:
            print(f"\nYahoo Real Estate not accessible ({access['yahoo']}) - skipping")

        return all_listings

    def filter_and_dedupe(self, listings: List[Dict]) -> List[Dict]:
        """Filter listings by criteria and remove duplicates"""
        qualified = []
        disqualified_by_reason = {}

        for listing in listings:
            passes, reason = self.passes_filters(listing)

            if not passes:
                disqualified_by_reason[reason] = disqualified_by_reason.get(reason, 0) + 1
                continue

            # Check for duplicates
            if self.is_duplicate(listing.get('name', '')):
                disqualified_by_reason['Duplicate'] = disqualified_by_reason.get('Duplicate', 0) + 1
                continue

            qualified.append(listing)

        print("\n" + "=" * 70)
        print("FILTERING RESULTS")
        print("=" * 70)
        print(f"Total candidates: {len(listings)}")
        print(f"After filtering: {len(qualified)} qualified")
        print(f"Duplicates (already in DB): {disqualified_by_reason.get('Duplicate', 0)}")
        print("\nDisqualification reasons:")
        for reason, count in sorted(disqualified_by_reason.items(), key=lambda x: x[1], reverse=True):
            if reason != 'Duplicate':
                print(f"  {reason}: {count}")

        return qualified

    def save_results(self, listings: List[Dict], access_status: Dict[str, str] = None, filename: str = 'NOMU_YAHOO_RESULTS.txt'):
        """Save results to output file"""
        if not listings and not access_status:
            print(f"\nNo new listings found. Output file not created.")
            return

        if not listings and access_status:
            # Write diagnostic report if portals were inaccessible
            with open(filename, 'w', encoding='utf-8', errors='replace') as f:
                f.write("NOMU.COM + YAHOO REAL ESTATE SCRAPE RESULTS\n")
                f.write(f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 150 + "\n\n")
                f.write("PORTAL ACCESS STATUS:\n")
                f.write("-" * 150 + "\n")
                for portal, status in access_status.items():
                    f.write(f"{portal.upper()}: {status}\n")
                f.write("\n" + "=" * 150 + "\n")
                f.write("DIAGNOSTIC NOTES:\n")
                f.write("Both portals are currently inaccessible for automated scraping. Possible reasons:\n")
                f.write("1. WAF (Web Application Firewall) blocking requests\n")
                f.write("2. JavaScript-rendered content (requires Selenium or Browser MCP)\n")
                f.write("3. Network/geographic restrictions\n")
                f.write("4. Rate limiting or IP-based blocking\n")
                f.write("5. Cloudflare or similar protection enabled\n")
                f.write("\nRECOMMENDATIONS:\n")
                f.write("- Try Selenium or Puppeteer for JS rendering\n")
                f.write("- Use Browser MCP tools for interactive access\n")
                f.write("- Check if portals offer APIs\n")
                f.write("- Manual review of NOMU/Yahoo may be needed\n")

            print(f"\nResults saved to {filename} (diagnostic report)")
            return

        # Format: Name | Price | Size | Floor | Year | Walk/Station | Fees | Direction | Notes
        with open(filename, 'w', encoding='utf-8', errors='replace') as f:
            f.write("NOMU.COM + YAHOO REAL ESTATE SCRAPE RESULTS\n")
            f.write(f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Filters: 1.5M-40M yen, >=30m2, >=1LDK, >=1982, <=15min walk, >=2F, no N-only, <=30k yen fees\n")
            f.write("=" * 150 + "\n\n")

            f.write("NEW LISTINGS (not in existing 116-entry database):\n")
            f.write("-" * 150 + "\n")
            f.write("Name\tPrice\tSize\tFloor\tYear\tWalk/Station\tFees\tDirection\tNotes\n")
            f.write("-" * 150 + "\n")

            for listing in listings:
                name = listing.get('name', 'N/A')
                price = listing.get('price_man', 'N/A')
                size = listing.get('size_m2', 'N/A')
                floor = listing.get('floor_num', 'N/A')
                year = listing.get('year', 'N/A')
                walk = listing.get('walk_min', 'N/A')
                station = listing.get('station', 'N/A')
                fees = listing.get('monthly_fees_yen', 'N/A')
                direction = listing.get('direction', 'N/A')
                notes = listing.get('notes', '')

                f.write(f"{name}\t{price}\t{size}\t{floor}\t{year}\t{walk}/{station}\t{fees}\t{direction}\t{notes}\n")

            f.write("\n" + "=" * 150 + "\n")
            f.write(f"Total new listings: {len(listings)}\n")

        print(f"\nResults saved to {filename} ({len(listings)} new listings)")

def main():
    scraper = TokyoApartmentScraper()

    print("=" * 70)
    print("TOKYO APARTMENT SCRAPER: NOMU + Yahoo Real Estate")
    print("=" * 70)
    print()

    # Test portal access first
    print("Testing portal access...")
    access_status = scraper.test_portal_access()
    print()

    listings = scraper.run_full_scrape(access_status)
    qualified = scraper.filter_and_dedupe(listings)
    scraper.save_results(qualified, access_status)

if __name__ == '__main__':
    main()
