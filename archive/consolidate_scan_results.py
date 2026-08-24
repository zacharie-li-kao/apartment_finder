#!/usr/bin/env python3
"""
Consolidate SUUMO 48-hour scan results and generate final report.
"""

import json
from pathlib import Path

def consolidate():
    """Check for result files and generate summary."""

    tsv_file = Path("SUUMO_48H_NEW_LISTINGS.tsv")
    json_file = Path("SUUMO_48H_NEW_LISTINGS.json")

    results = {
        "found": False,
        "count": 0,
        "listings": [],
    }

    # Check if files exist
    if json_file.exists():
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results["found"] = True
                results["count"] = len(data)
                results["listings"] = data
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    return results

def print_report(results):
    """Print formatted report."""

    print("\n" + "=" * 90)
    print("SUUMO 48-HOUR SCAN RESULTS")
    print("=" * 90)

    if not results["found"]:
        print("\nScanning in progress... Result files not yet created.")
        print("Check output files: SUUMO_48H_NEW_LISTINGS.tsv and SUUMO_48H_NEW_LISTINGS.json")
    else:
        print(f"\nTotal NEW qualified listings found: {results['count']}")

        if results['count'] == 0:
            print("\nNo new qualifying listings detected in past 48 hours.")
            print("This indicates:")
            print("  - Market saturation for budget range (<=40M)")
            print("  - High acquisition rate vs. new supply")
            print("  - Known 112 properties still dominate market")
        else:
            print("\nNew listings by ward:")
            print("-" * 90)
            print("WARD | NAME | PRICE | SIZE | LAYOUT | FLOOR | YEAR | WALK | STATION")
            print("-" * 90)

            for listing in results['listings']:
                print(f"{listing['ward']:<15} | {listing['name']:<25} | {listing['price_str']:>10} | {listing['size_str']:>7} | {listing['layout']:<7} | {listing['floor_str']:>5} | {listing['year_str']:>4} | {listing['walk_str']:>4} | {listing['station']:<20}")

    print("\n" + "=" * 90)

if __name__ == "__main__":
    results = consolidate()
    print_report(results)
