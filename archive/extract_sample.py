#!/usr/bin/env python3
import re
import json
import random
from pathlib import Path

# Read the index.html file
html_content = Path("index.html").read_text(encoding='utf-8')

# Extract all scoreboard entries (the <p class="new-scoreboard-entry"> blocks)
# Pattern: <p class="new-scoreboard-entry"><strong>#N NAME</strong> (Ward · Location) — Price · Details
scoreboard_start = html_content.find("<!-- SCOREBOARD_ENTRIES_START -->")
scoreboard_end = html_content.find("<!-- SCOREBOARD_ENTRIES_END -->")

if scoreboard_start == -1 or scoreboard_end == -1:
    print("ERROR: Could not find scoreboard section")
    exit(1)

scoreboard_section = html_content[scoreboard_start:scoreboard_end]

# Extract all <p> entries
p_pattern = r'<p class="new-scoreboard-entry"><strong>([^<]+)</strong>\s+\(([^)]+)\)\s+—\s+([^—]+?(?=—|$))'
matches = re.finditer(p_pattern, scoreboard_section)

listings = []
for match in matches:
    full_line = match.group(0)
    title_part = match.group(1)  # e.g., "#1 ガーデンプラザ柴又弐番館"
    location_part = match.group(2)  # e.g., "Katsushika · 柴又9分"
    details_part = match.group(3)  # Rest of the details

    # Parse the title to get number and name
    title_match = re.match(r'#?(\d+)?\s*(.+)', title_line:=title_part)
    if title_match:
        listing_num = title_match.group(1)
        name = title_match.group(2).strip()
    else:
        continue

    # Parse location: "Ward · Station/minutes"
    location_parts = [x.strip() for x in location_part.split('·')]
    ward = location_parts[0] if location_parts else ""
    station_walk = location_parts[1] if len(location_parts) > 1 else ""

    # Parse details to extract price, size, fees, occupancy
    # Pattern: PRICE · SIZE LAYOUT · YEAR · 費¥FEE/mo · DIRECTION · FLOOR · STATUS
    price_match = re.search(r'([0-9,]+万)', details_part)
    price = price_match.group(1) if price_match else ""

    size_match = re.search(r'(\d+(?:\.\d+)?m²)\s+([^·]+)', details_part)
    size = size_match.group(1) if size_match else ""
    layout = size_match.group(2) if size_match else ""

    year_match = re.search(r'(\d{4}年?(?:/\d)?)', details_part)
    year = year_match.group(1) if year_match else ""

    fees_match = re.search(r'費¥?([\d,]+)/mo', details_part)
    fees = fees_match.group(1) if fees_match else "未確認"

    occupancy = "Vacant" if "Vacant" in details_part or "空" in details_part else \
                "Occupied" if "Occupied" in details_part or "Tenant" in details_part else ""

    listings.append({
        'number': listing_num,
        'name': name,
        'ward': ward,
        'station_walk': station_walk,
        'price': price,
        'size': size,
        'layout': layout,
        'year': year,
        'fees': fees,
        'occupancy': occupancy,
        'full_line': full_line[:150]  # Store first 150 chars for reference
    })

# Random sample 20 listings
sample_size = min(20, len(listings))
sample = random.sample(listings, sample_size)

# Save sample to JSON for reference
with open("verification_sample.json", "w", encoding='utf-8') as f:
    json.dump(sample, f, indent=2, ensure_ascii=False)

# Write results to file instead of console
with open("verification_results.txt", "w", encoding='utf-8') as f:
    f.write(f"Total listings extracted: {len(listings)}\n")
    f.write(f"Random sample size: {sample_size}\n\n")
    f.write("Listings in sample:\n")
    f.write("=" * 100 + "\n")
    for i, listing in enumerate(sample, 1):
        f.write(f"{i:2d}. {listing['name']:30s} | {listing['ward']:15s} | {listing['price']:6s} | {listing['fees']:6s}/mo | {listing['occupancy']}\n")

print(f"Extracted {len(listings)} listings, sampled {sample_size}")
print("Results saved to verification_sample.json and verification_results.txt")
