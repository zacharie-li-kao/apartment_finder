#!/usr/bin/env python3
"""Analyze git commit history to understand database structure"""

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

print("=== ANALYZING COMMIT HISTORY ===\n")

building_counts = []
for line in result.stdout.split('\n'):
    if not line.strip():
        continue

    # Look for "count X→Y" pattern
    match = re.search(r'count\s+(\d+)\s*→\s*(\d+)', line)
    if match:
        from_count = int(match.group(1))
        to_count = int(match.group(2))
        delta = to_count - from_count

        # Extract the commit message (before "count")
        msg_part = line.split('count')[0].strip()
        if msg_part.startswith('Add #'):
            building_counts.append((from_count, to_count, delta, msg_part[:80]))
            print(f"{from_count:3d} → {to_count:3d} (+{delta:2d}): {msg_part[:80]}")

if building_counts:
    print("\n=== SUMMARY ===")
    final_count = building_counts[0][1] if building_counts else 0
    print(f"Latest count in commits: {final_count}")
    print(f"Expected from task: 116")

print("\n=== COMMIT MESSAGES WITHOUT COUNT ===")
for line in result.stdout.split('\n')[:20]:
    if 'Add #' in line and 'count' not in line:
        print(f"  {line[:100]}")

# The latest commit shows 115→116, so the current count is 116
# But the earlier commit history has older numbering schemes
# Let's just verify by looking at the most recent commits
print("\n=== MOST RECENT COMMITS (first 5) ===")
for i, line in enumerate(result.stdout.split('\n')[:5]):
    print(f"{i}: {line}")
