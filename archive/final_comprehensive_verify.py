#!/usr/bin/env python3
"""
Final comprehensive verification - extract URLs directly from index.html
"""
import json
import re
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

# Read index.html and extract scoreboard section
html_content = Path("index.html").read_text(encoding='utf-8')
scoreboard_start = html_content.find("<!-- SCOREBOARD_ENTRIES_START -->")
scoreboard_end = html_content.find("<!-- SCOREBOARD_ENTRIES_END -->")
scoreboard_section = html_content[scoreboard_start:scoreboard_end]

# Extract all listings with numbers and URLs
listings_map = {}
# Pattern: <p class="..."><strong>#NUM NAME</strong> (LOCATION) — DETAILS — <a href="URL"
p_pattern = r'<p class="new-scoreboard-entry"><strong>([^<]*?#(\d+)[^<]*?)\s+([^<]+)</strong>\s+\(([^)]+)\)\s+—\s+([^—]+?)—\s+<a href="([^"]+)"'

for match in re.finditer(p_pattern, scoreboard_section):
    full_strong = match.group(1)  # e.g., "#28 NAME"
    listing_num = match.group(2)  # e.g., "28"
    name = match.group(3).strip()  # NAME
    location = match.group(4).strip()  # e.g., "Katsushika · 青砥15分"
    details = match.group(5).strip()  # Price, size, etc.
    url = match.group(6).strip()  # URL

    listings_map[listing_num] = {
        'name': name,
        'location': location,
        'details': details,
        'url': url
    }

# Read sample
with open("verification_sample.json", "r", encoding="utf-8") as f:
    sample = json.load(f)

def normalize_price(price_str):
    """Normalize price: '2,950万' -> '2950'"""
    if not price_str:
        return None
    return re.sub(r'[,万\s]', '', price_str.strip())

def fetch_url(url):
    """Fetch URL"""
    try:
        req = urlopen(url, timeout=5)
        return req.read().decode('utf-8', errors='replace')
    except Exception:
        return None

def verify_listing(html, db_price, db_fees, portal):
    """Verify listing on portal"""
    if html is None or len(html) < 50:
        if portal == "HOME'S":
            return {"status": "⚠ WAF-blocked", "price": None, "fees": None}
        else:
            return {"status": "⚠ Fetch error", "price": None, "fees": None}

    # Check for delisted markers
    if re.search(r'掲載終了|この物件は現在ご紹介できません|見つかりませんでした|売却済み|削除されました', html):
        return {"status": "✗ Delisted", "price": None, "fees": None}

    # Try to extract price
    price = None
    price_patterns = [
        r'(\d+,?\d*万)',  # e.g., 2,950万 or 2950万
    ]
    for pattern in price_patterns:
        match = re.search(pattern, html)
        if match:
            price = match.group(1)
            break

    # Try to extract fees
    fees = None
    fees_patterns = [
        r'管理費\s*[:：]?\s*(\d+(?:,\d{3})?)',
        r'(\d+(?:,\d{3})?)円?/(?:月|mo)',
    ]
    for pattern in fees_patterns:
        match = re.search(pattern, html)
        if match:
            fees = match.group(1).replace(',', '')
            break

    # Determine status
    if price:
        price_match = normalize_price(price) == normalize_price(db_price)
        if fees:
            fees_match = fees == db_fees
        else:
            fees_match = False

        if price_match and fees_match:
            status = "✓ Active"
        else:
            status = "⚠ Active/Changed"
    else:
        status = "⚠ Data not extracted"

    return {"status": status, "price": price, "fees": fees}

# Build results
results = []
output = []
output.append("VERIFICATION RESULTS — 20 Random Listings from 116 Candidate Database")
output.append("=" * 145)
output.append(f"{'#':<4} {'Name':<26} {'Ward':<11} {'DB Price':<8} {'DB Fees':<8} {'Current Price':<14} {'Current Fees':<13} {'Status':<25}")
output.append("=" * 145)

active_ok = 0
active_changed = 0
delisted = 0
unable = 0

for item in sample:
    num = item['number']
    name_disp = item['name'][:24]
    ward = item['ward'][:10]
    db_price = item['price']
    db_fees = item['fees']

    # Get URL from listings_map
    if num not in listings_map:
        output.append(f"{num:<4} {name_disp:<26} {ward:<11} {db_price:<8} ¥{db_fees:<7} {'N/A':<14} {'N/A':<13} {'URL not found':<25}")
        unable += 1
        continue

    url_info = listings_map[num]
    url = url_info['url']
    portal = "SUUMO" if "suumo" in url.lower() else "HOME'S" if "homes" in url.lower() else "Other"

    # Fetch and verify
    html = fetch_url(url)
    result = verify_listing(html, db_price, db_fees, portal)

    status_str = result["status"]
    price_display = result["price"] if result["price"] else "N/A"
    fees_display = result["fees"] if result["fees"] else "N/A"

    # Count by status
    if "✓" in status_str:
        active_ok += 1
    elif "✗" in status_str:
        delisted += 1
    elif "⚠" in status_str:
        if "Active" in status_str:
            active_changed += 1
        else:
            unable += 1

    output.append(f"{num:<4} {name_disp:<26} {ward:<11} {db_price:<8} ¥{db_fees:<7} {price_display:<14} {fees_display:<13} {status_str:<25}")

output.append("=" * 145)
output.append(f"\nSUMMARY:")
output.append(f"  ✓ Active (all data confirmed): {active_ok}")
output.append(f"  ⚠ Active (price/fees differ): {active_changed}")
output.append(f"  ✗ Delisted: {delisted}")
output.append(f"  ⚠ Unable to verify (WAF/Network/etc): {unable}")
output.append(f"\nRESULT: {active_ok + active_changed} still listed, {delisted} delisted, {unable} unverifiable")

output_text = "\n".join(output)
with open("VERIFICATION_FINAL.txt", "w", encoding="utf-8") as f:
    f.write(output_text)

print(f"Done. Results: {active_ok} active, {active_changed} changed, {delisted} delisted, {unable} unable")
