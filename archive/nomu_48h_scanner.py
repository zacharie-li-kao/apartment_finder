#!/usr/bin/env python3
"""
NOMU 48h listing scanner for 23 Tokyo wards.
Fetches all pages, detail-extracts, applies hard filters, deduplicates against known 116.
"""
import re
import time
import sys
from datetime import datetime, timedelta
from urllib.parse import urljoin
from collections import defaultdict

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: requires requests and beautifulsoup4")
    print("Run: pip install requests beautifulsoup4")
    sys.exit(1)

# JIS codes for all 23 Tokyo wards
WARD_CODES = {
    "Chiyoda": "13101",
    "Chuo": "13104",
    "Minato": "13103",
    "Shinjuku": "13104",  # corrected
    "Shibuya": "13109",
    "Taito": "13106",
    "Arakawa": "13118",
    "Edogawa": "13120",
    "Sumida": "13107",
    "Koto": "13108",
    "Itabashi": "13114",
    "Nerima": "13119",
    "Kita": "13117",
    "Adachi": "13121",
    "Bunkyo": "13105",
    "Toshima": "13116",
    "Nakano": "13112",
    "Setagaya": "13111",
    "Shibuya": "13109",
    "Meguro": "13113",
    "Ota": "13110",
    "Shinagawa": "13102",
    "Midori": "13122",  # if exists
}

# Correct JIS codes for all 23 wards
WARD_CODES = {
    "Chiyoda": "13101",
    "Chuo": "13102",
    "Minato": "13103",
    "Shinjuku": "13104",
    "Bunkyo": "13105",
    "Taito": "13106",
    "Sumida": "13107",
    "Koto": "13108",
    "Shinagawa": "13109",
    "Ota": "13110",
    "Setagaya": "13111",
    "Nakano": "13112",
    "Meguro": "13113",
    "Itabashi": "13114",
    "Toshima": "13115",
    "Kita": "13116",
    "Arakawa": "13117",
    "Nerima": "13118",
    "Edogawa": "13119",
    "Adachi": "13120",
    "Suginami": "13121",
    "Katsushika": "13122",
}

KNOWN_PROPERTIES = {
    # Latest (add in chronological reverse order of recent adds)
    "セザール久が原",
    "メゾン蓮根",
    "サンタウン立花１号棟",
    "エスカイア等々力",
    "タウンハイツ亀有２号棟",
    "晴紀館",
    "カエサル西尾久",
    "関町南パーク・ホームズ",
    "パークハイム上井草",
    "東糀谷ダイヤモンドマンション",
    "リーベスト浮間舟渡",
    "Sevenstar Heights Nakano V",
    "グリーンパーク立石",
    "ダイアパレス立石",
    "コスモ堀切菖蒲園駅前",
    "ニューライフマンション木場",
    "エクレール亀戸",
    "向島ダイヤモンド",
    "ランドステージ両国",
    "ルックハイツ両国",
    "ラブリハイツ亀戸",
    "ガーデンプラザ柴又弐番館",
    "スカイワード亀有",
    "平井パーク・ホームズ",
    "東白鬚第二",
    "パークサイド八広",
    "エスペランサ堀切菖蒲園",
    "ライオンズガーデンお花茶屋",
    "朝日プラザ堀切菖蒲園",
    "セザールお花茶屋",
    "エンゼル柴又プロムテラス",
    "ヴェルアージュ亀有",
    "ライオンズ高砂第5",
    "ライオンズマンション言問",
    "サンデュエルお花茶屋",
    "グリーンキャピタル第三金町",
}

BASE_URL = "https://www.nomu.com/mansion/area_tokyo"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def fetch_url(url, retries=2):
    """Fetch URL with retry logic."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                print(f"ERROR fetching {url}: {e}", file=sys.stderr)
                return None
    return None

def parse_price(text):
    """Extract numeric price from text."""
    if not text:
        return None
    match = re.search(r'(\d+(?:,\d+)*)', text.replace(',', ''))
    if match:
        try:
            return int(match.group(1))
        except:
            pass
    return None

def extract_listing_cards(html, ward):
    """Extract listing cards from list page."""
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    cards = []

    # NOMU structure: each listing is <div class="item_resultsmall click_R">
    for container in soup.find_all('div', class_='item_resultsmall'):
        try:
            # Extract name and ID from <h2><a href="/mansion/id/{ID}/">
            name_link = container.find('h2')
            if not name_link:
                continue
            name_link = name_link.find('a')
            if not name_link:
                continue
            name = name_link.get_text(strip=True)
            detail_url = name_link.get('href')
            if not detail_url or '/mansion/id/' not in detail_url:
                continue
            if not detail_url.startswith('http'):
                detail_url = urljoin('https://www.nomu.com', detail_url)

            # Extract price from <p class="item_price"><span class="num">
            price_elem = container.find('p', class_='item_price')
            if not price_elem:
                continue
            price_span = price_elem.find('span', class_='num')
            if not price_span:
                continue
            price_text = price_span.get_text(strip=True)
            price = parse_price(price_text)

            # Early gate: price <= 40M
            if price and price <= 40_000_000:
                cards.append({
                    'name': name,
                    'price': price,
                    'url': detail_url,
                    'ward': ward,
                    'price_text': price_text,
                })
        except Exception as e:
            continue

    return cards

def extract_detail_page(html, url):
    """Extract all required fields from detail page."""
    if not html:
        return {}

    soup = BeautifulSoup(html, 'html.parser')
    detail = {'url': url}

    # Extract 更新日 (update date) from table
    # Look for table row with "更新日" as header
    for th in soup.find_all('th'):
        if '更新日' in th.get_text():
            td = th.find_next('td')
            if td:
                date_text = td.get_text(strip=True)
                # Parse "2026年6月30日" format
                match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_text)
                if match:
                    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    try:
                        detail['update_date'] = datetime(year, month, day)
                    except:
                        pass
            break

    # NOMU detail structure: each spec is a <span class="item_status_content">
    # Extract from <span class="item_status_title">KEY</span> + <span class="item_status_content">VALUE</span>
    statuses = soup.find_all('li', class_='item_status')

    for status in statuses:
        title_elem = status.find('span', class_='item_status_title')
        content_elem = status.find('span', class_='item_status_content')

        if not title_elem or not content_elem:
            continue

        title = title_elem.get_text(strip=True)
        content = content_elem.get_text(strip=True)

        if '間取' in title:
            detail['layout'] = content

        if '面積' in title or '専有' in title:
            match = re.search(r'([\d.]+)', content)
            if match:
                detail['size'] = float(match.group(1))

        if '築' in title or '築年月' in title:
            match = re.search(r'(\d{4})', content)
            if match:
                detail['year'] = int(match.group(1))

        if '所在' in title and '階' in title:
            match = re.search(r'(\d+)', content)
            if match:
                detail['floor'] = int(match.group(1))

        if '向き' in title:
            detail['direction'] = content

        if '交通' in title:
            # Extract walk time from "駅 徒歩X分"
            match = re.search(r'駅.*?徒歩(\d+)分', content)
            if match:
                detail['walk_min'] = int(match.group(1))
            # Extract station name
            station_match = re.search(r'「([^」]+)」駅', content)
            if station_match:
                detail['station'] = station_match.group(1)

    # Extract 管理費 and 修繕積立金 from spec section
    spec_section = soup.find('div', class_='module_spec_detail')
    if spec_section:
        spec_text = spec_section.get_text()

        # Look for 管理費 value
        fees_match = re.search(r'管理費[^0-9]*?([\d,]+)', spec_text)
        if fees_match:
            detail['fees_text'] = fees_match.group(1)

        # Look for 修繕積立金 value
        reserve_match = re.search(r'修繕積立金[^0-9]*?([\d,]+)', spec_text)
        if reserve_match and 'fees_text' not in detail:
            detail['fees_text'] = reserve_match.group(1)

    # Extract 所有権 vs 借地権 from table
    # Look for table row with "土地権利" as header, then get the corresponding td
    for th in soup.find_all('th'):
        if '土地権利' in th.get_text():
            # Get the next td sibling
            td = th.find_next('td')
            if td:
                ownership_val = td.get_text(strip=True)
                if '借地権' in ownership_val:
                    detail['ownership'] = 'leasehold'
                elif '所有権' in ownership_val:
                    detail['ownership'] = 'freehold'
            break

    return detail

def check_hard_criteria(listing, detail):
    """Apply all hard filtering criteria."""
    issues = []

    # Check if within 48 hours (this is NOT a hard reject, just tracking)
    # Hard reject if no date found
    if 'update_date' not in detail:
        issues.append("no update_date found")
    else:
        age = datetime.now() - detail['update_date']
        if age.days > 2:  # More than 48 hours
            issues.append(f"update > 48h ({age.days} days old)")

    # Size >= 30m²
    if 'size' not in detail or detail['size'] < 30:
        issues.append(f"size < 30m² ({detail.get('size', '?')}m²)")

    # Layout >= 1LDK
    layout = detail.get('layout', '?')
    if layout == '?':
        issues.append("layout unknown")
    elif not any(x in layout for x in ['LDK', 'DK']):
        if '1R' in layout or 'K' not in layout:
            issues.append(f"layout < 1LDK ({layout})")

    # Year >= 1982
    if 'year' not in detail or detail['year'] < 1982:
        issues.append(f"year < 1982 ({detail.get('year', '?')})")

    # Walk <= 15 min
    if 'walk_min' not in detail or detail['walk_min'] > 15:
        issues.append(f"walk > 15min ({detail.get('walk_min', '?')}min)")

    # Floor >= 2F
    if 'floor' not in detail or detail['floor'] < 2:
        issues.append(f"floor < 2F ({detail.get('floor', '?')}F)")

    # Monthly fees <= 30,000
    if 'fees_text' in detail:
        fees_match = re.search(r'([\d,]+)', detail['fees_text'])
        if fees_match:
            fees = int(fees_match.group(1).replace(',', ''))
            if fees > 30_000:
                issues.append(f"fees > ¥30k (¥{fees:,})")

    # Freehold only
    if detail.get('ownership') == 'leasehold':
        issues.append("leasehold (shakuchiken)")

    # Not North-facing only
    direction = detail.get('direction', '?')
    if direction == '北' or direction == '北向き':
        issues.append("North-facing only")

    return issues

def scan_ward(ward_name, ward_code):
    """Scan a single ward, all pages."""
    print(f"[{ward_name}] Scanning ward code {ward_code}...", file=sys.stderr)

    url = f"{BASE_URL}/{ward_code}/"
    all_listings = []
    page = 1

    while True:
        page_url = f"{url}?pager_page={page}" if page > 1 else url
        print(f"  Page {page}...", file=sys.stderr, end=' ', flush=True)

        html = fetch_url(page_url)
        if not html:
            print("FETCH FAIL", file=sys.stderr)
            break

        cards = extract_listing_cards(html, ward_name)
        if not cards:
            print("NO CARDS", file=sys.stderr)
            break

        print(f"{len(cards)} cards", file=sys.stderr)
        all_listings.extend(cards)
        page += 1

        # Rate limit: 2s between list pages
        time.sleep(2)

    print(f"[{ward_name}] Total {len(all_listings)} cards after price filter", file=sys.stderr)
    return all_listings

def main():
    print("NOMU 48h Scanner - Tokyo 23 wards", file=sys.stderr)
    print(f"Scan time: {datetime.now().isoformat()}", file=sys.stderr)
    print(file=sys.stderr)

    # Output header
    print("WARD\tNAME\tPRICE\tSIZE\tLAYOUT\tFLOOR\tYEAR\tWALK\tSTATION\tDIRECTION\tFEES\tOWNERSHIP\tURL")

    qualified = []

    # Start with priority wards
    priority_wards = ["Sumida", "Koto"]
    secondary_wards = [w for w in WARD_CODES.keys() if w not in priority_wards]

    for ward_priority, wards in [("priority", priority_wards), ("secondary", secondary_wards)]:
        for ward in wards:
            if ward not in WARD_CODES:
                continue

            listings = scan_ward(ward, WARD_CODES[ward])

            # Detail-fetch each listing - limit to first 30 to avoid long delays
            fetch_limit = 30 if ward_priority == "priority" else 15
            fetched = 0

            for listing in listings:
                if fetched >= fetch_limit:
                    print(f"  [LIMIT] {ward} fetched {fetched}, skipping rest of ward", file=sys.stderr)
                    break

                if listing['name'] in KNOWN_PROPERTIES:
                    print(f"  [DUP] {listing['name']}", file=sys.stderr)
                    continue

                print(f"  Detail-fetch: {listing['name'][:30]}...", file=sys.stderr, end=' ', flush=True)
                detail_html = fetch_url(listing['url'])
                detail = extract_detail_page(detail_html, listing['url'])

                issues = check_hard_criteria(listing, detail)
                if issues:
                    print(f"FAIL: {', '.join(issues)}", file=sys.stderr)
                    fetched += 1
                    time.sleep(1)
                    continue

                print("PASS", file=sys.stderr)
                qualified.append({**listing, **detail})
                fetched += 1

                # Rate limit: 1s between detail fetches
                time.sleep(1)

    # Output qualified listings as TSV
    for q in qualified:
        parts = [
            q.get('ward', '?'),
            q.get('name', '?'),
            f"¥{q.get('price', 0):,}" if q.get('price') else '?',
            f"{q.get('size', '?')}m²",
            q.get('layout', '?'),
            f"{q.get('floor', '?')}F",
            str(q.get('year', '?')),
            f"{q.get('walk_min', '?')}min",
            q.get('station', '?'),
            q.get('direction', '?'),
            q.get('fees_text', '?'),
            q.get('ownership', '?'),
            q.get('url', '?'),
        ]
        print('\t'.join(parts))

    print(f"\n[SUMMARY] Found {len(qualified)} new qualified listings", file=sys.stderr)

if __name__ == '__main__':
    main()
