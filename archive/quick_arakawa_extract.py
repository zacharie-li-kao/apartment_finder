#!/usr/bin/env python3
"""Quick Arakawa extraction from SUUMO"""

import subprocess
import requests
from bs4 import BeautifulSoup
import re
import time
import json

# Extract Arakawa listings from SUUMO
def scrape_arakawa():
    candidates = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept-Language': 'ja,en;q=0.9',
    })

    for page in range(1, 50):  # Pages 1-50, stop early if no results
        try:
            url = f'https://suumo.jp/ms/chuko/tokyo/sc_arakawa/?page={page}'

            # Use curl
            cmd = ['curl', '-s', url, '-H', 'User-Agent: Mozilla/5.0']
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=15)

            if result.returncode != 0:
                print(f"[Page {page}] Curl failed")
                break

            soup = BeautifulSoup(result.stdout, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'/ms/chuko/tokyo/sc_arakawa/nc_\d+'))

            if not links:
                print(f"[Page {page}] No listings found - stopping")
                break

            print(f"[Page {page}] Found {len(links)} listings")

            for link in links:
                try:
                    detail_url = link.get('href', '')
                    if not detail_url.startswith('http'):
                        detail_url = 'https://suumo.jp' + detail_url

                    # Extract building name from link text
                    name = link.get_text().strip()
                    if name and len(name) > 2:
                        candidates.append({
                            'name': name,
                            'url': detail_url,
                            'portal': 'SUUMO'
                        })
                except:
                    continue

            time.sleep(0.5)

        except Exception as e:
            print(f"[Page {page}] Error: {e}")
            break

    return candidates

if __name__ == '__main__':
    print("Scraping Arakawa from SUUMO...")
    results = scrape_arakawa()

    # Remove duplicates
    seen = set()
    unique = []
    for r in results:
        if r['name'] not in seen:
            seen.add(r['name'])
            unique.append(r)

    print(f"\nTotal extracted: {len(results)}")
    print(f"Unique: {len(unique)}")

    # Save results
    with open(r'C:\Users\zakat\Desktop\apartment\arakawa_extracted.json', 'w', encoding='utf-8') as f:
        json.dump(unique[:31], f, ensure_ascii=False, indent=2)  # First 31

    print("\nSample results:")
    for r in unique[:5]:
        print(f"  - {r['name']}")
        print(f"    URL: {r['url']}")
