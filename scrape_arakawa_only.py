#!/usr/bin/env python3
"""Quick Arakawa scrape - get listing names and SUUMO URLs"""

import subprocess
import json
import re
from bs4 import BeautifulSoup
from collections import defaultdict

def scrape_arakawa_listings():
    """Scrape Arakawa SUUMO listing page 1-3"""
    listings = []

    for page in range(1, 4):
        try:
            url = f'https://suumo.jp/ms/chuko/tokyo/sc_arakawa/?page={page}'
            cmd = ['curl', '-s', url, '-H', 'User-Agent: Mozilla/5.0']
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=10)

            if result.returncode != 0:
                print(f"Page {page}: curl failed")
                break

            soup = BeautifulSoup(result.stdout, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'/ms/chuko/tokyo/sc_arakawa/nc_\d+'))

            if not links:
                print(f"Page {page}: no listings")
                break

            print(f"Page {page}: found {len(links)} listings")

            for link in links:
                href = link.get('href', '')
                name = link.get_text().strip()

                if name and href and len(name) > 2:
                    full_url = 'https://suumo.jp' + href if not href.startswith('http') else href
                    listings.append({
                        'name': name,
                        'url': full_url
                    })

        except Exception as e:
            print(f"Page {page}: error {e}")
            break

    # Deduplicate by name
    seen = {}
    for item in listings:
        if item['name'] not in seen:
            seen[item['name']] = item

    return list(seen.values())[:31]  # First 31 unique

if __name__ == '__main__':
    print("Scraping Arakawa SUUMO listings...")
    results = scrape_arakawa_listings()
    print(f"\nFound {len(results)} unique listings\n")

    # Save as JSON
    with open(r'C:\Users\zakat\Desktop\apartment\arakawa_listings_quick.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Show first 10
    print("First 10 listings:")
    for i, r in enumerate(results[:10], 1):
        print(f"{i}. {r['name']}")
        print(f"   {r['url']}")

    print(f"\n✓ Saved {len(results)} listings to arakawa_listings_quick.json")
