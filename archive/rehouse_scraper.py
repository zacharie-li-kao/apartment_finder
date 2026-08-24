#!/usr/bin/env python3
"""
Scrape Rehouse Koto-ku apartment listings
"""
import re
import sys
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13108/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def parse_price(price_str):
    """Parse price string and return numeric value in 万円"""
    if not price_str:
        return None
    price_str = price_str.strip()
    # Remove whitespace and yen symbols
    price_str = re.sub(r'[\s円,]', '', price_str)

    # Check if it contains "million"
    if 'million' in price_str.lower():
        # Parse format like "152 million yen" -> convert to 万円
        match = re.search(r'(\d+(?:\.\d+)?)\s*million', price_str, re.IGNORECASE)
        if match:
            return int(float(match.group(1)) * 100)

    # Try to parse as direct number
    try:
        # If ends with 万, it's already in 万円 format
        if '万' in price_str:
            return int(float(price_str.replace('万', '')))
        # Otherwise convert from yen
        value = int(price_str)
        if value > 10000:  # Likely in full yen, convert to 万円
            return value // 10000
        return value
    except:
        return None

def parse_size(size_str):
    """Parse size from string like '86.48㎡'"""
    if not size_str:
        return None
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎡|m²)', size_str)
    if match:
        return float(match.group(1))
    return None

def parse_floor(floor_str):
    """Parse floor from string like '19th floor' or '19階'"""
    if not floor_str:
        return None, None
    # Try to extract floor number and total floors
    match = re.search(r'(\d+)(?:st|nd|rd|th)?(?:\s*(?:floor|階))?(?:\s*/\s*(\d+))?', floor_str, re.IGNORECASE)
    if match:
        current = match.group(1)
        total = match.group(2) if match.group(2) else None
        return current, total
    return None, None

def parse_year(year_str):
    """Parse year from string like 'Built January 2014'"""
    if not year_str:
        return None
    match = re.search(r'(\d{4})', year_str)
    if match:
        return int(match.group(1))
    return None

def parse_walk_time(walk_str):
    """Parse walk time from string like '7-minute walk'"""
    if not walk_str:
        return None
    match = re.search(r'(\d+)\s*(?:-)?(?:minute|分)', walk_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def parse_station(station_str):
    """Parse station name from address/station info"""
    if not station_str:
        return None
    # Extract station name before 'Station' or '駅'
    match = re.search(r'([^/]+?)\s*(?:Station|駅)', station_str)
    if match:
        return match.group(1).strip()
    return station_str.strip()

def scrape_page(page_num=1):
    """Scrape a single page of listings"""
    url = BASE_URL
    params = {'page': page_num} if page_num > 1 else {}

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')

        listings = []

        # Find all listing cards - they appear to be in divs with class containing 'item' or similar
        # Let's look for the listing containers
        cards = soup.find_all('div', {'class': re.compile(r'.*item.*', re.IGNORECASE)})

        if not cards:
            # Try alternative selector
            cards = soup.find_all('article')

        if not cards:
            # Try looking for links with specific pattern
            cards = soup.find_all('div', {'class': re.compile(r'.*mansion.*', re.IGNORECASE)})

        print(f"Found {len(cards)} cards on page {page_num}")

        return soup
    except Exception as e:
        print(f"Error scraping page {page_num}: {e}")
        return None

def scrape_all_listings():
    """Main function to scrape all listings"""
    all_listings = []

    for page in range(1, 10):  # 246 listings = ~9 pages
        print(f"\nScraping page {page}...")
        soup = scrape_page(page)

        if not soup:
            break

        # Get the page text for analysis
        time.sleep(1)  # Be respectful with requests

    return all_listings

if __name__ == '__main__':
    scrape_all_listings()
