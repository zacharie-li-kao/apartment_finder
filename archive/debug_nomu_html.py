#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

url = "https://www.nomu.com/mansion/area_tokyo/13107/"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

try:
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    html = r.text

    # Save raw HTML for inspection
    with open("C:\\Users\\zakat\\Desktop\\apartment\\nomu_sumida_page.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("HTML saved to nomu_sumida_page.html")

    soup = BeautifulSoup(html, 'html.parser')

    # Look for common listing containers
    print("\n=== Searching for listing containers ===\n")

    # Try various selectors
    for selector in ['div.item_table', 'div.mansion_item', 'div.item', 'li.item',
                     'article', 'div[class*="item"]', 'div[class*="mansion"]']:
        matches = soup.select(selector)
        if matches:
            print(f"Found {len(matches)} matches for: {selector}")
            if matches:
                print(f"  First match HTML:\n{str(matches[0])[:300]}...\n")

    # List all div classes
    print("\n=== All unique div classes ===")
    classes = set()
    for div in soup.find_all('div', limit=100):
        cls = div.get('class')
        if cls:
            classes.add(' '.join(cls))

    for cls in sorted(list(classes)[:20]):
        print(f"  {cls}")

except Exception as e:
    print(f"ERROR: {e}")
