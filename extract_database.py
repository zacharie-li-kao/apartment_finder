#!/usr/bin/env python3
"""Extract the 116 existing buildings from git commit history"""

import subprocess
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

result = subprocess.run(
    ['git', 'log', '--all', '--format=%s'],
    cwd='C:\\Users\\zakat\\Desktop\\apartment',
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

buildings = set()
adds = 0
removes = 0

for line in result.stdout.split('\n'):
    # Skip empty lines
    if not line.strip():
        continue

    # Count adds
    if 'Add #' in line:
        adds += 1

        # Extract building name from "Add #N Name (location...)" pattern
        # Matches: Add #126 セザール久が原 (Ota · ...)
        match = re.search(r'^Add #[\d\-]+\s+([^(·\n]+?)(?:\s*\(|$)', line)
        if match:
            name = match.group(1).strip()
            if name and len(name) > 1:
                buildings.add(name)

    # Count removes
    if 'Remove #' in line or 'remove' in line.lower():
        removes += 1

print(f"Git log processing:")
print(f"  Add commits: {adds}")
print(f"  Remove mentions: {removes}")
print(f"  Unique buildings extracted: {len(buildings)}")
print()

# Show the extracted buildings
print("Extracted buildings (first 50):")
for i, building in enumerate(sorted(list(buildings))[:50]):
    print(f"  {i+1}. {building}")

# Count and verify
print(f"\nTotal extracted: {len(buildings)}")
print(f"Note: Expected ~116 based on latest commit, got {len(buildings)}")
print(f"Difference may be due to:")
print(f"  - Remove operations")
print(f"  - Complex multi-add parsing")
print(f"  - Parsing errors on edge cases")

# Save to file for reuse
with open('database_extracted.txt', 'w', encoding='utf-8', errors='replace') as f:
    for building in sorted(buildings):
        f.write(building + '\n')

print(f"\nSaved {len(buildings)} buildings to database_extracted.txt")
