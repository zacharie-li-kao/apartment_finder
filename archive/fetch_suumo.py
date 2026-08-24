#!/usr/bin/env python3
import requests
import re
import json
import sys
from urllib.parse import urljoin

# Wards to search: Toshima, Bunkyo, Chiyoda, Shinjuku
WARDS = {
    'toshima': 'sc_toshima',
    'bunkyo': 'sc_bunkyo',
    'chiyoda': 'sc_chiyoda',
    'shinjuku': 'sc_shinjuku'
}

BASE_URL = 'https://suumo.jp/ms/chuko/tokyo/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = 'utf-8'
        return resp.text
    except Exception as e:
        print(f"Error fetching: {e}", file=sys.stderr)
        return None

def extract_property_links(html):
    pattern = r'href="(/ms/chuko/tokyo/[^"]*nc_\d+/)"'
    matches = re.findall(pattern, html)
    return [urljoin(BASE_URL, match) for match in matches]

def extract_detail_info(html, url):
    info = {'url': url}
    
    # Floor
    floor_match = re.search(r'>(\d+)階<', html)
    if floor_match:
        info['floor'] = int(floor_match.group(1))
    
    # Management fee
    mgmt_match = re.search(r'管理費[：:\s]+([0-9,]+)\s*円', html)
    if mgmt_match:
        try:
            info['mgmt_fee'] = int(mgmt_match.group(1).replace(',', ''))
        except:
            pass
    
    # Reserve fund
    reserve_match = re.search(r'修繕積立金[：:\s]+([0-9,]+)\s*円', html)
    if reserve_match:
        try:
            info['reserve_fee'] = int(reserve_match.group(1).replace(',', ''))
        except:
            pass
    
    # Ownership
    if '所有権' in html:
        info['ownership'] = '所有権'
    elif '借地権' in html:
        info['ownership'] = '借地権'
    
    return info

results = {}
for ward_name, ward_code in WARDS.items():
    print(f"Searching {ward_name}...", file=sys.stderr)
    results[ward_name] = []
    
    for page in range(1, 3):  # First 2 pages for testing
        url = f"{BASE_URL}{ward_code}/?page={page}"
        html = fetch_page(url)
        if not html:
            break
        
        links = extract_property_links(html)
        print(f"  Page {page}: {len(links)} properties", file=sys.stderr)
        
        for i, link in enumerate(links[:3]):  # Test first 3 properties per page
            detail_html = fetch_page(link)
            if detail_html:
                detail = extract_detail_info(detail_html, link)
                results[ward_name].append(detail)
            if i >= 2:
                break
    
    print(f"  Total processed: {len(results[ward_name])}", file=sys.stderr)

# Output summary
for ward, props in results.items():
    print(f"{ward}: {len(props)} properties fetched")
    for p in props[:2]:
        print(f"  - Floor: {p.get('floor', 'N/A')}, Mgmt: {p.get('mgmt_fee', 'N/A')}, Reserve: {p.get('reserve_fee', 'N/A')}, Own: {p.get('ownership', 'N/A')}")

