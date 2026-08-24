#!/usr/bin/env python3
"""
Merge search results from parallel agents.
Reads PASS/FAIL lines, de-dups against existing listings, generates commit entries.
"""

import re
import sys
from collections import defaultdict
from datetime import datetime

def parse_pass_line(line):
    """Parse PASS|Name|Price|Size|Floor|Year|Walk|Station|Fees|Layout|Direction|URL"""
    if not line.startswith('PASS|'):
        return None
    parts = line[5:].split('|')
    if len(parts) < 11:
        return None
    return {
        'name': parts[0].strip(),
        'price_man': parts[1].strip(),  # without 万
        'size_m2': parts[2].strip(),
        'floor': parts[3].strip(),
        'year': parts[4].strip(),
        'walk_min': parts[5].strip(),
        'station': parts[6].strip(),
        'fees': parts[7].strip(),  # numeric only
        'layout': parts[8].strip(),
        'direction': parts[9].strip(),
        'url': parts[10].strip() if len(parts) > 10 else '',
    }

def parse_fail_line(line):
    """Parse FAIL|Name|Reason|Price|Size|Year|Station|URL"""
    if not line.startswith('FAIL|'):
        return None
    parts = line[5:].split('|')
    if len(parts) < 7:
        return None
    return {
        'name': parts[0].strip(),
        'reason': parts[1].strip(),
        'price_man': parts[2].strip(),
        'size_m2': parts[3].strip(),
        'year': parts[4].strip(),
        'station': parts[5].strip(),
        'url': parts[6].strip() if len(parts) > 6 else '',
    }

def read_existing_names():
    """Extract all existing building names from index.html and listings.html"""
    names = set()
    try:
        with open('C:\\Users\\zakat\\Desktop\\apartment\\index.html') as f:
            content = f.read()
            # Extract from scoreboard entries: <strong>#N BuildingName</strong>
            for match in re.finditer(r'<strong>#\d+\s+(.+?)</strong>', content):
                names.add(match.group(1).strip())
    except:
        pass

    try:
        with open('C:\\Users\\zakat\\Desktop\\apartment\\listings.html') as f:
            content = f.read()
            # Extract from table links: <a href=...>BuildingName</a>
            for match in re.finditer(r'<a href="[^"]*"[^>]*>(.+?)</a>', content):
                name = match.group(1).strip()
                if name and not name.startswith('http'):
                    names.add(name)
    except:
        pass

    return names

def format_commit_entry(listing, num):
    """Format a listing for commit message"""
    entry = f"Add #{num} {listing['name']} ("

    # Infer ward from URL or station hints
    ward = "Unknown-ku"
    if 'sumida' in listing.get('url', '').lower() or 'sc_sumida' in listing.get('url', ''):
        ward = "Sumida"
    elif 'koto' in listing.get('url', '').lower() or 'sc_koto' in listing.get('url', ''):
        ward = "Koto"

    entry += f"{ward} · {listing['station']} {listing['walk_min']}分 · "
    entry += f"{listing['price_man']}万 · {listing['size_m2']} {listing['layout']} · "
    entry += f"{listing['floor']} · {listing['year']} · "
    entry += f"¥{listing['fees']}/mo · {listing['direction']}"
    entry += ")"

    return entry

def main():
    existing_names = read_existing_names()
    print(f"Found {len(existing_names)} existing listings to de-dup against")
    print(f"Existing names sample: {list(existing_names)[:5]}")

    # Read from stdin or agent results
    pass_listings = []
    fail_listings = []

    # For now, just show the structure
    print("\nReady to process agent results. Waiting for input...")
    print("Expected format:")
    print("  PASS|Name|Price|Size|Floor|Year|Walk|Station|Fees|Layout|Direction|URL")
    print("  FAIL|Name|Reason|Price|Size|Year|Station|URL")

if __name__ == '__main__':
    main()
