#!/usr/bin/env python3
"""
Comprehensive verification of all 20 sampled listings
"""
import json
import re
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import sys

# Read the verification sample data
with open("verification_sample.json", "r", encoding="utf-8") as f:
    sample = json.load(f)

# Read the index.html to extract URLs for each listing number
html_content = Path("index.html").read_text(encoding='utf-8')
scoreboard_start = html_content.find("<!-- SCOREBOARD_ENTRIES_START -->")
scoreboard_end = html_content.find("<!-- SCOREBOARD_ENTRIES_END -->")
scoreboard_section = html_content[scoreboard_start:scoreboard_end]

# Build map of listing number -> URL
listings_urls = {}
p_pattern = r'<p class="new-scoreboard-entry"><strong>#?(\d+)\s+([^<]+)</strong>\s+\(([^)]+)\)\s+—\s+([^—]+?)—\s+<a href="([^"]+)"'
for match in re.finditer(p_pattern, scoreboard_section):
    num = match.group(1)
    name = match.group(2).strip()
    location = match.group(3).strip()
    details = match.group(4).strip()
    url = match.group(5).strip()

    listings_urls[num] = {
        'name': name,
        'url': url
    }

def fetch_url(url):
    """Fetch URL with timeout"""
    try:
        req = urlopen(url, timeout=5)
        return req.read().decode('utf-8', errors='replace')
    except:
        return None

def check_active(html_content):
    """Check if listing is still active"""
    if html_content is None:
        return "⚠ Unable to fetch"

    # Check for delisted markers
    if re.search(r'掲載終了|この物件は現在ご紹介できません|売却済み|削除されました', html_content):
        return "✗ Delisted"

    # Check if price/data block exists
    if not re.search(r'(\d{1,4},?\d{0,3}万|円|価格)', html_content):
        return "⚠ Data not found (WAF?)"

    return "✓ Active"

def extract_price(html_content):
    """Extract price from HTML"""
    if html_content is None:
        return None

    patterns = [
        r'価格\s*[:：]\s*(\d{1,4}(?:,\d{3})?万)',
        r'(\d{1,4}(?:,\d{3})?万)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_content)
        if match:
            return match.group(1)
    return None

def extract_fees(html_content):
    """Extract monthly fees from HTML"""
    if html_content is None:
        return None

    patterns = [
        r'管理費(?:・修繕積立金)?\s*[:：]\s*(\d{1,3}(?:,\d{3})?)',
        r'([0-9]+),?([0-9]+)円?/(?:月|mo)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_content)
        if match:
            return match.group(1).replace(',', '')
    return None

results = []
output = ["VERIFICATION RESULTS — 20 Random Listings\n"]
output.append("=" * 120)
output.append(f"{'#':<4} {'Name':<30} {'Ward':<12} {'DB Price':<8} {'Current':<8} {'Fees Match':<15} {'Status':<20}\n")
output.append("=" * 120)

for item in sample:
    num = item['number']
    name = item['name'][:28]
    ward = item['ward'][:12]
    db_price = item['price']
    db_fees = item['fees']

    # Get URL
    url_info = listings_urls.get(num, {'url': 'Not found'})
    url = url_info['url']

    # Fetch and verify
    html = fetch_url(url)
    status = check_active(html)
    current_price = extract_price(html)
    current_fees = extract_fees(html)

    # Compare
    price_match = "✓ Match" if current_price and current_price.replace(',', '') == db_price.replace(',', '') else \
                  "⚠ Change" if current_price else "⚠ N/A"

    fees_match = "✓ Match" if current_fees and current_fees == db_fees else \
                 "⚠ Change" if current_fees else "⚠ N/A"

    # Determine result status
    if status == "✓ Active" and price_match == "✓ Match" and fees_match == "✓ Match":
        final_status = "✓ Active"
    elif status == "✗ Delisted":
        final_status = "✗ Delisted"
    elif status == "⚠ Unable to fetch":
        final_status = "⚠ WAF/Unable"
    else:
        final_status = "⚠ Price/Fees change"

    # Format output line
    current_display = current_price if current_price else "N/A"
    fees_display = fees_match if current_fees else "N/A"

    output.append(f"{num:<4} {name:<30} {ward:<12} {db_price:<8} {current_display:<8} {fees_display:<15} {final_status:<20}")

    results.append({
        'number': num,
        'name': name,
        'db_price': db_price,
        'current_price': current_price,
        'price_status': price_match,
        'db_fees': db_fees,
        'current_fees': current_fees,
        'fees_status': fees_match,
        'final_status': final_status,
        'url': url
    })

output.append("=" * 120)

# Summary
active_count = sum(1 for r in results if "✓" in r['final_status'])
delisted_count = sum(1 for r in results if "✗" in r['final_status'])
unable_count = sum(1 for r in results if "⚠" in r['final_status'])

output.append(f"\nSUMMARY:")
output.append(f"  Active (all OK): {active_count}")
output.append(f"  Delisted: {delisted_count}")
output.append(f"  Unable to verify/Price changes: {unable_count}")

# Write output
output_text = "\n".join(output)
with open("verification_results_full.txt", "w", encoding="utf-8") as f:
    f.write(output_text)

print(f"Verified 20 listings. Results: {active_count} active, {delisted_count} delisted, {unable_count} unable/changed")
print("Full results saved to verification_results_full.txt")
