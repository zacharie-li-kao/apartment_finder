#!/usr/bin/env python3
"""
Final verification: 20 listings check
"""
import json
import re
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

# Read sample
with open("verification_sample.json", "r", encoding="utf-8") as f:
    sample = json.load(f)

# Read HTML and extract URLs
html_content = Path("index.html").read_text(encoding='utf-8')
scoreboard_start = html_content.find("<!-- SCOREBOARD_ENTRIES_START -->")
scoreboard_end = html_content.find("<!-- SCOREBOARD_ENTRIES_END -->")
scoreboard_section = html_content[scoreboard_start:scoreboard_end]

# Build URL map
listings_urls = {}
p_pattern = r'<p class="new-scoreboard-entry"><strong>#?(\d+)\s+([^<]+)</strong>\s+\(([^)]+)\)\s+—\s+([^—]+?)—\s+<a href="([^"]+)"'
for match in re.finditer(p_pattern, scoreboard_section):
    listings_urls[match.group(1)] = match.group(5).strip()

def normalize_price(price_str):
    """Normalize price for comparison: '2,950万' -> '2950'"""
    if not price_str:
        return None
    return re.sub(r'[,万\s]', '', price_str.strip())

def fetch_url(url):
    """Fetch URL"""
    try:
        req = urlopen(url, timeout=5)
        return req.read().decode('utf-8', errors='replace')
    except:
        return None

def verify_suumo(html, db_price, db_fees):
    """Verify SUUMO listing"""
    if html is None:
        return {"status": "⚠ Fetch error"}

    # Check for delisted
    if re.search(r'掲載終了|この物件は現在ご紹介できません|見つかりませんでした', html):
        return {"status": "✗ Delisted"}

    # Try to find price - look for 価格 or just numbers with 万
    price = None
    price_match = re.search(r'価格\s*[:：]\s*(\d+(?:,\d{3})?万)', html)
    if price_match:
        price = price_match.group(1)
    elif re.search(r'\d{1,4},?\d{0,3}万', html):  # Fallback: price exists somewhere
        price = "found"

    # Try to find fees
    fees = None
    fees_match = re.search(r'管理費\s*[:：]?\s*(\d+(?:,\d{3})?)', html)
    if fees_match:
        fees = fees_match.group(1)

    # Compare prices
    if price:
        db_norm = normalize_price(db_price)
        price_norm = normalize_price(price)
        price_ok = db_norm == price_norm if (db_norm and price_norm) else "Unable"

        if price_ok == True:
            price_status = "✓ Match"
        elif price_ok == False:
            price_status = f"⚠ {price_norm} vs {db_norm}"
        else:
            price_status = "⚠ Format unclear"
    else:
        price_status = "⚠ No price found"

    # Compare fees
    if fees:
        fees_ok = fees == db_fees
        fees_status = "✓ Match" if fees_ok else f"⚠ {fees} vs {db_fees}"
    else:
        fees_status = "⚠ Not found"

    return {
        "status": "✓ Active",
        "price_status": price_status,
        "fees_status": fees_status
    }

def verify_homes(html, db_price):
    """Verify HOME'S listing"""
    if html is None or len(html) < 100:
        return {"status": "⚠ WAF-blocked"}

    # Check for delisted
    if re.search(r'掲載終了|売却済み|削除されました', html):
        return {"status": "✗ Delisted"}

    return {"status": "⚠ HOME'S (AWS WAF) - Manual check needed"}

results = []
output = []
output.append("VERIFICATION RESULTS — 20 Random Listings from 116 Database")
output.append("=" * 130)
output.append(f"{'#':<4} {'Name':<28} {'Ward':<12} {'DB Price':<8} {'DB Fees':<8} {'Price Status':<15} {'Fees Status':<15} {'Overall Status':<20}")
output.append("=" * 130)

active_ok = 0
active_changed = 0
delisted = 0
unable = 0

for item in sample:
    num = item['number']
    name = item['name'][:26]
    ward = item['ward'][:11]
    db_price = item['price']
    db_fees = item['fees']

    url = listings_urls.get(num, "")
    portal = "SUUMO" if "suumo.jp" in url else "HOME'S" if "homes" in url else "Other"

    html = fetch_url(url)

    if "suumo" in url.lower():
        result = verify_suumo(html, db_price, db_fees)
    elif "homes" in url.lower():
        result = verify_homes(html, db_price)
    else:
        result = {"status": "⚠ Unknown portal"}

    status = result["status"]
    price_status = result.get("price_status", "-")
    fees_status = result.get("fees_status", "-")

    # Determine overall
    if status == "✓ Active":
        if "✓" in price_status and "✓" in fees_status:
            overall = "✓ Active"
            active_ok += 1
        else:
            overall = "⚠ Active/Changed"
            active_changed += 1
    elif status == "✗ Delisted":
        overall = "✗ Delisted"
        delisted += 1
    else:
        overall = status
        unable += 1

    output.append(f"{num:<4} {name:<28} {ward:<12} {db_price:<8} ¥{db_fees:<7} {price_status:<15} {fees_status:<15} {overall:<20}")

    results.append({
        'num': num,
        'name': item['name'],
        'overall': overall,
        'portal': portal
    })

output.append("=" * 130)
output.append(f"\nSUMMARY:")
output.append(f"  ✓ Active (all data confirmed): {active_ok}")
output.append(f"  ⚠ Active but price/fees changed: {active_changed}")
output.append(f"  ✗ Delisted: {delisted}")
output.append(f"  ⚠ Unable to verify (HOME'S WAF-blocked, network error, etc): {unable}")
output.append(f"\nTotal: {active_ok + active_changed} still listed, {delisted} delisted, {unable} unverifiable")

output_text = "\n".join(output)
with open("final_verification_report.txt", "w", encoding="utf-8") as f:
    f.write(output_text)

# Write summary to stdout
print(f"Active: {active_ok}, Changed: {active_changed}, Delisted: {delisted}, Unable: {unable}")
