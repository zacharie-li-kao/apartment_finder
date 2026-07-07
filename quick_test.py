#!/usr/bin/env python3
import requests
import time

# Test NOMU with corrected URL pattern
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# Test 1: Main page
print("Test 1: Main page")
url = "https://www.nomu.com/"
try:
    resp = session.get(url, timeout=10)
    print(f"  Status: {resp.status_code}")
except Exception as e:
    print(f"  Error: {e}")

time.sleep(2)

# Test 2: Ward page with pager_page parameter
print("\nTest 2: Ward listing with ?pager_page=1")
url = "https://www.nomu.com/mansion/area_tokyo/13107/?pager_page=1"
try:
    resp = session.get(url, timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Length: {len(resp.content)} bytes")
    if resp.status_code == 200 and len(resp.content) > 1000:
        print("  SUCCESS - Got valid response with content")
        # Check for listing indicators
        if 'mansion' in resp.text.lower() or 'item_table' in resp.text:
            print("  Found listing HTML patterns")
    else:
        print(f"  ERROR - Invalid response (status={resp.status_code}, len={len(resp.content)})")
except Exception as e:
    print(f"  Error: {e}")

time.sleep(2)

# Test 3: Try without pager_page parameter
print("\nTest 3: Ward listing without pager_page parameter (default page 1)")
url = "https://www.nomu.com/mansion/area_tokyo/13107/"
try:
    resp = session.get(url, timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Length: {len(resp.content)} bytes")
except Exception as e:
    print(f"  Error: {e}")
