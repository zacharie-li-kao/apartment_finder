#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build comprehensive existing listings database from git history
"""

import subprocess
import re
import json
from typing import Set, List, Dict

def extract_listings_from_git() -> Set[str]:
    """Extract all property names and codes from git log"""
    listings = set()

    try:
        result = subprocess.run(
            ['git', 'log', '--pretty=format:%s', '--all'],
            capture_output=True,
            text=True,
            cwd='C:\\Users\\zakat\\Desktop\\apartment'
        )

        for line in result.stdout.split('\n'):
            # Pattern 1: "Add #N PropertyName (details)"
            match = re.search(r'Add #\d+ ([^(]+)\s*\(', line)
            if match:
                name = match.group(1).strip()
                listings.add(name)
                print(f"[+] {name}")

            # Pattern 2: Property names in other commit messages
            # Look for Japanese property names in brackets or after colons
            for word in ['Add', 'Remove', '✓', '⭐']:
                if word in line:
                    # Try to extract Japanese text
                    japanese_words = re.findall(r'[一-鿿぀-ゟ゠-ヿ]+', line)
                    for jp_word in japanese_words:
                        if len(jp_word) > 2 and jp_word not in ['について', 'から', 'など']:
                            listings.add(jp_word)
                            print(f"[+] {jp_word}")

    except Exception as e:
        print(f"[ERROR] Failed to extract from git: {e}")

    return listings

def save_database(listings: Set[str]):
    """Save to JSON and text formats"""

    # Sort by length (longer names tend to be more specific)
    sorted_listings = sorted(listings, key=len, reverse=True)

    # Save as JSON
    with open('C:\\Users\\zakat\\Desktop\\apartment\\EXISTING_LISTINGS_DB.json', 'w', encoding='utf-8') as f:
        json.dump({
            'count': len(sorted_listings),
            'listings': sorted_listings,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    # Save as text (one per line)
    with open('C:\\Users\\zakat\\Desktop\\apartment\\EXISTING_LISTINGS_DB.txt', 'w', encoding='utf-8') as f:
        f.write(f"# EXISTING LISTINGS DATABASE\n")
        f.write(f"# Total: {len(sorted_listings)} properties\n")
        f.write(f"# Generated: {__import__('datetime').datetime.now().isoformat()}\n\n")
        for name in sorted_listings:
            f.write(f"{name}\n")

    print(f"\n[INFO] Saved {len(sorted_listings)} listings to database files")
    return sorted_listings

if __name__ == '__main__':
    print("Building existing listings database from git history...\n")
    listings = extract_listings_from_git()
    sorted_listings = save_database(listings)
    print(f"\nDatabase files created:")
    print(f"  JSON: EXISTING_LISTINGS_DB.json")
    print(f"  Text: EXISTING_LISTINGS_DB.txt")
