#!/usr/bin/env python3
"""
Final verification: extract URLs from sample's full_line field
"""
import json
import re
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

# Read sample
with open("verification_sample.json", "r", encoding="utf-8") as f:
    sample = json.load(f)

def normalize_price(price_str):
    """Normalize price: '2,950万' -> '2950'"""
    if not price_str:
        return None
    return re.sub(r'[,万\s]', '', price_str.strip())

def fetch_url(url):
    """Fetch URL with timeout"""
    try:
        req = urlopen(url, timeout=5)
        return req.read().decode('utf-8', errors='replace')
    except Exception:
        return None

def extract_url_from_html(full_line):
    """Extract URL from HTML snippet in full_line"""
    match = re.search(r'href="([^"]+)"', full_line)
    return match.group(1) if match else None

def verify_portal(html, db_price, db_fees, portal):
    """Verify listing on portal"""
    if html is None or len(html) < 100:
        if portal == "homes":
            return ("WAF", None, None)
        else:
            return ("Fetch error", None, None)

    # Check for delisted (Japanese text)
    if re.search(r'掲載終了|この物件は現在ご紹介できません|見つかりませんでした|売却済み|削除されました', html):
        return ("Delisted", None, None)

    # For active listings, try to extract price and fees
    price = None
    fees = None

    # Try price extraction
    price_match = re.search(r'(\d+,?\d*万)', html)
    if price_match:
        price = price_match.group(1)

    # Try fees extraction
    fees_match = re.search(r'管理費\s*[:：]?\s*(\d+(?:,\d{3})?)', html)
    if fees_match:
        fees = fees_match.group(1)

    return ("Active", price, fees)

results = []
output = []
output.append("VERIFICATION RESULTS — 20 Random Listings from 116 Candidate Database")
output.append("=" * 140)
output.append(f"{'#':<4} {'Name':<26} {'Ward':<11} {'DB Price':<8} {'DB Fees':<8} {'Current Price':<13} {'Current Fees':<12} {'Status':<25}")
output.append("=" * 140)

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
    full_line = item['full_line']

    # Extract URL from full_line
    url = extract_url_from_html(full_line)
    if not url:
        output.append(f"{num:<4} {name_disp:<26} {ward:<11} {db_price:<8} ¥{db_fees:<7} {'N/A':<13} {'N/A':<12} {'No URL found':<25}")
        unable += 1
        continue

    # Determine portal
    if "suumo" in url.lower():
        portal = "SUUMO"
    elif "homes" in url.lower():
        portal = "HOME'S"
    else:
        portal = "Other"

    # Fetch and verify
    html = fetch_url(url)
    status_str, current_price, current_fees = verify_portal(html, db_price, db_fees, portal)

    # Determine comparison result
    if status_str == "Active":
        price_display = current_price if current_price else "N/A"
        fees_display = current_fees if current_fees else "N/A"

        # Check if price matches (after normalization)
        if current_price:
            price_match = normalize_price(db_price) == normalize_price(current_price)
        else:
            price_match = None

        # Check if fees match
        if current_fees:
            fees_match = db_fees == current_fees
        else:
            fees_match = None

        if price_match and fees_match:
            final_status = "✓ Active (OK)"
            active_ok += 1
        else:
            final_status = "⚠ Active/Changed"
            active_changed += 1
    elif status_str == "Delisted":
        final_status = "✗ Delisted"
        price_display = "N/A"
        fees_display = "N/A"
        delisted += 1
    else:
        final_status = f"⚠ {status_str}"
        price_display = "N/A"
        fees_display = "N/A"
        unable += 1

    output.append(f"{num:<4} {name_disp:<26} {ward:<11} {db_price:<8} ¥{db_fees:<7} {price_display:<13} {fees_display:<12} {final_status:<25}")

output.append("=" * 140)
output.append(f"\nSUMMARY:")
output.append(f"  ✓ Active (all data confirmed): {active_ok}")
output.append(f"  ⚠ Active (price or fees changed): {active_changed}")
output.append(f"  ✗ Delisted: {delisted}")
output.append(f"  ⚠ Unable to verify: {unable}")
output.append(f"\nTOTAL STILL LISTED: {active_ok + active_changed} | DELISTED: {delisted} | UNVERIFIABLE: {unable}")

output_text = "\n".join(output)
with open("verification_table.txt", "w", encoding="utf-8") as f:
    f.write(output_text)

print(f"Completed verification. Results saved.")
