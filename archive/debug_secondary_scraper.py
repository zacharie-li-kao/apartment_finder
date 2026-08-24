#!/usr/bin/env python3
"""
Debug script to test SUUMO and Rehouse parsing
"""

import requests
from bs4 import BeautifulSoup
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def test_suumo_page():
    """Test SUUMO page fetching and parsing"""
    print("=" * 80)
    print("TESTING SUUMO - Arakawa Ward")
    print("=" * 80)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Arakawa ward code: 13118
    url = 'https://suumo.jp/ms/chuko/Tokyo/13118/?page=1'
    print(f"Fetching: {url}\n")

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"Status: {resp.status_code}")

        soup = BeautifulSoup(resp.content, 'html.parser')

        # Try to find any links to detail pages
        detail_links = soup.find_all('a', href=re.compile(r'/ms/chuko/tokyo/.*nc_\d+/'))
        print(f"Found {len(detail_links)} detail links")

        if detail_links:
            print(f"\nFirst 5 detail links:")
            for i, link in enumerate(detail_links[:5]):
                href = link.get('href', '')
                print(f"  {i+1}. {href}")

            # Try fetching the first detail page
            if detail_links:
                first_detail_url = detail_links[0].get('href', '')
                if not first_detail_url.startswith('http'):
                    first_detail_url = 'https://suumo.jp' + first_detail_url

                print(f"\nFetching first detail page: {first_detail_url}")
                detail_resp = requests.get(first_detail_url, headers=headers, timeout=15)
                print(f"Detail page status: {detail_resp.status_code}")

                detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
                detail_text = detail_soup.get_text()

                print(f"\nDetail page text (first 1000 chars):")
                print(detail_text[:1000])

                # Try to extract some fields
                print(f"\nField extraction attempts:")
                title = detail_soup.find('title')
                if title:
                    print(f"  Title: {title.get_text()}")

                h1 = detail_soup.find('h1')
                if h1:
                    print(f"  H1: {h1.get_text(strip=True)}")

                # Look for price
                price_match = re.search(r'(\d+),?(\d{0,3})\s*万', detail_text)
                if price_match:
                    print(f"  Price found: {price_match.group(0)}")

                # Look for size
                size_match = re.search(r'(\d+\.?\d*)\s*(?:m[²2m]|㎡)', detail_text)
                if size_match:
                    print(f"  Size found: {size_match.group(0)}")

                # Look for year
                year_match = re.search(r'(19|20)(\d{2})\s*年', detail_text)
                if year_match:
                    print(f"  Year found: {year_match.group(0)}")

                # Look for floor
                floor_match = re.search(r'(\d+)\s*階', detail_text)
                if floor_match:
                    print(f"  Floor found: {floor_match.group(0)}")

        else:
            print("No detail links found!")
            # Try alternative search patterns
            print("\nSearching for any links...")
            all_links = soup.find_all('a', href=True)
            print(f"Total links found: {len(all_links)}")
            if all_links:
                print("Sample links:")
                for link in all_links[:10]:
                    print(f"  {link.get('href')}")

    except Exception as e:
        print(f"Error: {e}")


def test_rehouse_page():
    """Test Rehouse page fetching and parsing"""
    print("\n" + "=" * 80)
    print("TESTING REHOUSE - Arakawa Ward")
    print("=" * 80)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Arakawa ward code: 13118
    url = 'https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13118/'
    print(f"Fetching: {url}\n")

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"Status: {resp.status_code}")

        soup = BeautifulSoup(resp.content, 'html.parser')

        # Try to find any links to detail pages
        detail_links = soup.find_all('a', href=re.compile(r'/bkdetail/'))
        print(f"Found {len(detail_links)} detail links")

        if detail_links:
            print(f"\nFirst 5 detail links:")
            for i, link in enumerate(detail_links[:5]):
                href = link.get('href', '')
                print(f"  {i+1}. {href}")

            # Try fetching the first detail page
            if detail_links:
                first_detail_url = detail_links[0].get('href', '')
                if not first_detail_url.startswith('http'):
                    first_detail_url = 'https://www.rehouse.co.jp' + first_detail_url

                print(f"\nFetching first detail page: {first_detail_url}")
                detail_resp = requests.get(first_detail_url, headers=headers, timeout=15)
                print(f"Detail page status: {detail_resp.status_code}")

                detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
                detail_text = detail_soup.get_text()

                print(f"\nDetail page text (first 1000 chars):")
                print(detail_text[:1000])

                # Try to extract some fields
                print(f"\nField extraction attempts:")
                title = detail_soup.find('title')
                if title:
                    print(f"  Title: {title.get_text()}")

                h1 = detail_soup.find('h1')
                if h1:
                    print(f"  H1: {h1.get_text(strip=True)}")

                # Look for price
                price_match = re.search(r'(\d+),?(\d{0,3})\s*万', detail_text)
                if price_match:
                    print(f"  Price found: {price_match.group(0)}")

                # Look for size
                size_match = re.search(r'(\d+\.?\d*)\s*(?:m[²2m]|㎡)', detail_text)
                if size_match:
                    print(f"  Size found: {size_match.group(0)}")

        else:
            print("No detail links found!")
            print("\nSearching for any links...")
            all_links = soup.find_all('a', href=True)
            print(f"Total links found: {len(all_links)}")
            if all_links:
                print("Sample links:")
                for link in all_links[:10]:
                    print(f"  {link.get('href')}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    test_suumo_page()
    test_rehouse_page()
