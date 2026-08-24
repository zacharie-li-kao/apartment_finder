#!/usr/bin/env python3
"""Extract all building names from git history"""

import subprocess
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Get git log
result = subprocess.run(['git', 'log', '--all', '--format=%B'],
                       capture_output=True, text=True, encoding='utf-8')
commits = result.stdout

# Extract all "Add #NNN" and "Remove #NNN" entries
buildings = set()

# Pattern: Add or Remove followed by building name (up to next parenthesis or semicolon)
for match in re.finditer(r'(?:Add|Remove) #\d+\s+([^（\n;]+)', commits):
    name = match.group(1).strip()
    # Remove trailing junk
    name = re.sub(r'\s+\(.+$', '', name)  # Remove anything after (
    name = re.sub(r'\s+·.+$', '', name)  # Remove anything after ·
    if name:
        buildings.add(name)

print(f"Found {len(buildings)} unique building names:")
print()

for name in sorted(buildings):
    print(name)

print(f"\nTotal: {len(buildings)}")
print("\nAs Python set:")
print("EXISTING_BUILDINGS = {")
for name in sorted(buildings):
    print(f"    '{name}',")
print("}")
