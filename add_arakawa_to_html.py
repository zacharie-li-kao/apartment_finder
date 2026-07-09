#!/usr/bin/env python3
"""
Parse Arakawa results from script output and add to index.html
Usage: python add_arakawa_to_html.py
"""

import re
import sys
from pathlib import Path

def extract_arakawa_results(output_file):
    """Extract Arakawa results table from script output"""
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find Arakawa section in RESULTS
    # Pattern: "Arakawa (N candidates):" followed by header line, dashes, then rows
    pattern = r'^Arakawa \((\d+) candidates\):\n.*?\n-+\n(.*?)(?=\n^[A-Z]|\nNo qualifying|\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        print("ERROR: Could not find Arakawa results section")
        return []

    count = int(match.group(1))
    results_text = match.group(2)

    candidates = []
    for line in results_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('-'):
            continue

        # Parse line: Portal | Name | Price | Size | Layout | Floor | Year | Walk | Station | Fees | Dir | Ownership
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 12:
            continue

        try:
            cand = {
                'portal': parts[0],
                'name': parts[1],
                'price_str': parts[2],      # e.g., "¥2780万"
                'size_str': parts[3],        # e.g., "41.32m²"
                'layout': parts[4],
                'floor': parts[5],           # e.g., "2F"
                'year': parts[6],
                'walk': parts[7],            # e.g., "9m"
                'station': parts[8],
                'fees_str': parts[9],        # e.g., "¥25170"
                'direction': parts[10],
                'ownership': parts[11],
            }

            # Extract price in millions for consistency
            price_match = re.search(r'¥?([\d.]+)M', cand['price_str'])
            if price_match:
                cand['price_display'] = f"{price_match.group(1)}万"
            else:
                cand['price_display'] = cand['price_str']

            candidates.append(cand)
        except Exception as e:
            print(f"  Warning: Could not parse line: {line[:60]}...")
            continue

    print(f"Extracted {len(candidates)} Arakawa candidates (expected {count})")
    return candidates

def candidate_to_html_row(cand, portal_url_map=None):
    """Convert candidate dict to HTML table row"""
    portal_url_map = portal_url_map or {}

    # Determine row class
    row_class = 'pass'
    flags_parts = []

    # Arakawa is deprioritized per CLAUDE.md
    flags_parts.append('<span class="flag yellow">Arakawa (deprioritized)</span>')
    row_class = 'warn'

    # Add ownership flag if freehold
    if cand['ownership'] == 'Freehold':
        flags_parts.insert(0, '<span class="flag green">Freehold</span>')

    flags_html = ''.join(flags_parts)

    # Try to get portal URL
    url = portal_url_map.get(cand['name'], '#')
    if url == '#' and cand['portal'] == 'SUUMO':
        # Fallback: construct URL from name if not found
        url = '#'

    html = f'''    <tr class="{row_class}" data-added="2026-07-09">
      <td><a href="{url}" target="_blank">{cand['name']}</a></td>
      <td class="price">{cand['price_display']}</td>
      <td>{cand['size_str']}</td>
      <td>{cand['floor']}</td>
      <td>{cand['year']}</td>
      <td>{cand['walk']}</td>
      <td>{cand['station']}</td>
      <td>{cand['fees_str']}</td>
      <td>{cand['layout']}</td>
      <td>{cand['direction']}</td>
      <td>{flags_html}</td>
    </tr>'''

    return html

def update_html(html_file, arakawa_candidates):
    """Add Arakawa candidates to index.html"""
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Find the Arakawa section markers
    start_marker = '    <!-- ARAKAWA_ROWS_START -->'
    end_marker = '    <!-- ARAKAWA_ROWS_END -->'

    start_idx = html_content.find(start_marker)
    end_idx = html_content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find Arakawa markers in HTML")
        return False

    # Build new rows
    new_rows = '\n'.join(candidate_to_html_row(c) for c in arakawa_candidates)

    # Keep the existing one candidate that was already there
    existing_section = html_content[start_idx + len(start_marker):end_idx]

    # Replace just the new candidates, keep existing one
    new_section = f"{start_marker}\n{existing_section}\n{new_rows}\n    {end_marker}"

    # Update HTML
    html_content = html_content[:start_idx] + new_section + html_content[end_idx + len(end_marker):]

    # Update Arakawa count (1 existing + N new = 1 + N total)
    arakawa_count = 1 + len(arakawa_candidates)
    old_count = f'id="count-arakawa">1 viable'
    new_count = f'id="count-arakawa">{arakawa_count} viable'
    html_content = html_content.replace(old_count, new_count)

    # Update total candidate count in summary
    # Current is 116, will become 116 + N
    total_count = 116 + len(arakawa_candidates)
    old_total = 'strong id="candidate-count">116 viable'
    new_total = f'strong id="candidate-count">{total_count} viable'
    html_content = html_content.replace(old_total, new_total)

    # Write back
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Updated index.html: {arakawa_count} Arakawa total, {total_count} overall")
    return True

if __name__ == '__main__':
    output_file = r'C:\Users\zakat\Desktop\apartment\results_output_raw.txt'
    html_file = r'C:\Users\zakat\Desktop\apartment\index.html'

    # Extract results
    candidates = extract_arakawa_results(output_file)
    if not candidates:
        print("FATAL: No candidates extracted")
        sys.exit(1)

    print(f"\nSample candidates:")
    for c in candidates[:3]:
        print(f"  {c['name']}: {c['price_display']}, {c['size_str']}, {c['floor']}")

    # Update HTML
    if update_html(html_file, candidates):
        print("\n✓ HTML updated successfully")
    else:
        print("\n✗ Failed to update HTML")
        sys.exit(1)
