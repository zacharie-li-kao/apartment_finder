#!/usr/bin/env python3
"""Parse Arakawa results from script output and format for HTML"""

import re
import sys

def parse_results_table(output_text):
    """Extract Arakawa results from script output table"""
    arakawa_candidates = []

    # Find Arakawa section
    arakawa_match = re.search(r'Arakawa \(\d+ candidates\):(.*?)(?=\n\w+:|$)', output_text, re.DOTALL)
    if not arakawa_match:
        return []

    arakawa_section = arakawa_match.group(1)

    # Skip header line
    lines = arakawa_section.split('\n')[2:]

    for line in lines:
        if not line.strip() or line.startswith('-'):
            continue

        # Parse: Portal | Name | Price | Size | Layout | Floor | Year | Walk | Station | Fees | Dir | Ownership
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 12:
            continue

        try:
            cand = {
                'portal': parts[0],
                'name': parts[1],
                'price_str': parts[2],  # e.g., "¥2780万"
                'size_str': parts[3],   # e.g., "41.32m²"
                'layout': parts[4],
                'floor': parts[5],      # e.g., "2F"
                'year': parts[6],
                'walk': parts[7],       # e.g., "9m"
                'station': parts[8],
                'fees_str': parts[9],   # e.g., "¥25k"
                'direction': parts[10],
                'ownership': parts[11],
            }
            arakawa_candidates.append(cand)
        except:
            continue

    return arakawa_candidates

def format_html_row(cand, portal_urls):
    """Format candidate as HTML table row"""
    # Try to find portal URL
    portal_url = portal_urls.get(cand['name'], '#')

    # Parse price (from "¥XXXX万" to "XXXX万")
    price_display = re.sub(r'^¥', '', cand.get('price_str', ''))

    # Determine row class based on criteria
    row_class = 'pass'  # Default to pass, will refine based on flags
    flags_html = ''

    # Check for warnings/flags
    if 'Arakawa' in cand.get('direction', '') or '荒川' in cand.get('station', ''):
        # Arakawa is deprioritized
        flags_html += '<span class="flag yellow">Arakawa (deprioritized)</span>'
        row_class = 'warn'

    flags_html = f'<span class="flag green">freehold</span>{flags_html}' if cand.get('ownership') == 'Freehold' else flags_html

    html = f'''    <tr class="{row_class}" data-added="2026-07-09">
      <td><a href="{portal_url}" target="_blank">{cand['name']}</a></td>
      <td class="price">{price_display}</td>
      <td>{cand.get('size_str', '?')}</td>
      <td>{cand.get('floor', '?')}</td>
      <td>{cand.get('year', '?')}</td>
      <td>{cand.get('walk', '?')}</td>
      <td>{cand.get('station', '?')}</td>
      <td>{cand.get('fees_str', '?')}</td>
      <td>{cand.get('layout', '?')}</td>
      <td>{cand.get('direction', '?')}</td>
      <td>{flags_html}</td>
    </tr>'''

    return html

if __name__ == '__main__':
    # Read output file
    try:
        with open(r'C:\Users\zakat\Desktop\apartment\results_output_raw.txt', 'r', encoding='utf-8') as f:
            output_text = f.read()
    except:
        print("ERROR: Could not read results_output_raw.txt")
        sys.exit(1)

    candidates = parse_results_table(output_text)
    print(f"Parsed {len(candidates)} Arakawa candidates")

    for i, cand in enumerate(candidates[:5], 1):
        print(f"\n#{i}: {cand['name']}")
        print(f"  Price: {cand['price_str']}, Size: {cand['size_str']}, Floor: {cand['floor']}")
        print(f"  Walk: {cand['walk']}, Station: {cand['station']}, Fees: {cand['fees_str']}")
