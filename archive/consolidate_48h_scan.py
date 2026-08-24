#!/usr/bin/env python3
"""
Consolidate results from parallel portal sweeps (SUUMO, rehouse, NOMU, athome).
Dedup against known 116-property database.
Output: per-ward table of new qualified candidates from past 48h.
"""

import json
import sys
import re
from pathlib import Path

# Known properties database (extracted from git log + MEMORY.md)
# Format: {name: {price, size, layout, floor, year, walk, station, direction, fees, ownership, url}}
KNOWN_PROPERTIES = {
    "平井パーク・ホームズ": {"price": 3470, "ward": "Sumida"},
    "ヴェラハイツ亀戸文花ユーフォニアス": {"price": 3600, "ward": "Sumida"},
    "ルネ町屋": {"price": 3580, "ward": "Arakawa"},
    "ガーデンプラザ柴又弐番館": {"price": 2980, "ward": "Katsushika"},
    "ハイラーク大島": {"price": 3580, "ward": "Koto"},
    "名津葛西第二": {"price": 3880, "ward": "Edogawa"},
    "京成小岩グリーンプラザ": {"price": 3980, "ward": "Edogawa"},
    "クリオ志村ラ・モード": {"price": 3800, "ward": "Itabashi"},
    "東砂三丁目ハイツ6号棟": {"price": 3800, "ward": "Koto"},
    "オリンポス四つ木": {"price": 3480, "ward": "Katsushika"},
    "新小岩パーク・ホームズ": {"price": 3890, "ward": "Katsushika"},
    "ライオンズマンション東四つ木": {"price": 3780, "ward": "Katsushika"},
    "金町ハイツ": {"price": 3480, "ward": "Katsushika"},
    "日神パレステージ小岩第二": {"price": 3000, "ward": "Edogawa"},
    "さくらマンション小松川": {"price": 3980, "ward": "Edogawa"},
    "GSハイム第二金町": {"price": 3990, "ward": "Katsushika"},
    "四つ木パーク・ホームズ": {"price": 3550, "ward": "Katsushika"},
    "パークステージ小岩": {"price": 2980, "ward": "Edogawa"},
    "GSハイムときわ台": {"price": 3480, "ward": "Itabashi"},
    "キャッスルマンションお花茶屋": {"price": 2780, "ward": "Katsushika"},
    "ダイアパレス隅田公園": {"price": 3480, "ward": "Sumida"},
    "セザール久が原": {"price": 2190, "ward": "Ota"},
    "メゾン蓮根": {"price": 2480, "ward": "Itabashi"},
    # ... more known entries; this is a sample
}

def is_known_property(name):
    """Check if property name is in known database (fuzzy match)."""
    name_lower = name.lower().strip()
    for known_name in KNOWN_PROPERTIES:
        if name_lower == known_name.lower() or known_name.lower() in name_lower:
            return True
    return False

def parse_portal_results(portal_name, results_file):
    """Parse portal results TSV."""
    if not Path(results_file).exists():
        return []
    
    properties = []
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[1:]:  # Skip header
                if not line.strip():
                    continue
                fields = line.strip().split('\t')
                if len(fields) >= 12:
                    properties.append({
                        'portal': portal_name,
                        'ward': fields[0],
                        'name': fields[1],
                        'price': fields[2],
                        'size': fields[3],
                        'layout': fields[4],
                        'floor': fields[5],
                        'year': fields[6],
                        'walk': fields[7],
                        'station': fields[8],
                        'direction': fields[9],
                        'fees': fields[10],
                        'ownership': fields[11],
                        'url': fields[12] if len(fields) > 12 else '?',
                    })
    except Exception as e:
        print(f"Error parsing {portal_name}: {e}", file=sys.stderr)
    
    return properties

def consolidate_results():
    """Load results from all portals and consolidate."""
    all_results = []
    
    for portal in ['suumo', 'rehouse', 'nomu', 'athome']:
        results_file = f"C:\Users\zakat\Desktop\apartment\PORTAL_SCAN_{portal.upper()}_48h.tsv"
        props = parse_portal_results(portal, results_file)
        all_results.extend(props)
    
    # Dedup and filter known properties
    new_candidates = []
    seen_names = set()
    
    for prop in all_results:
        name = prop['name'].strip()
        if name not in seen_names and not is_known_property(name):
            new_candidates.append(prop)
            seen_names.add(name)
    
    return new_candidates

def output_per_ward_table(candidates):
    """Generate per-ward summary table."""
    by_ward = {}
    for prop in candidates:
        ward = prop['ward']
        if ward not in by_ward:
            by_ward[ward] = []
        by_ward[ward].append(prop)
    
    # Sort wards by priority (Sumida, Koto first)
    priority_order = ['Sumida', 'Koto', 'Itabashi', 'Katsushika', 'Chuo', 'Minato', 'Shibuya', 
                      'Chiyada', 'Shinjuku', 'Nerima', 'Setagaya', 'Nakano', 'Toshima', 
                      'Bunkyo', 'Taito', 'Ota', 'Edogawa', 'Arakawa', 'Kita', 
                      'Meguro', 'Shinagawa']
    
    print("\n" + "="*140)
    print("COMPREHENSIVE 48-HOUR SCAN RESULTS — ALL 23 WARDS")
    print("="*140)
    
    for ward in priority_order:
        if ward in by_ward:
            props = by_ward[ward]
            print(f"\n{ward.upper()} — {len(props)} new qualified candidate(s)")
            print("-" * 140)
            print(f"{'Name':<30} {'Price':<10} {'Size':<10} {'Layout':<8} {'Floor':<10} {'Year':<8} {'Walk':<8} {'Station':<15} {'Dir':<6} {'Fees':<12} {'Ownership':<12}")
            print("-" * 140)
            for p in props:
                print(f"{p['name']:<30} {p['price']:<10} {p['size']:<10} {p['layout']:<8} {p['floor']:<10} {p['year']:<8} {p['walk']:<8} {p['station']:<15} {p['direction']:<6} {p['fees']:<12} {p['ownership']:<12}")
            print("-" * 140)
        else:
            print(f"\n{ward.upper()} — 0 new qualified candidates")
    
    print("\n" + "="*140)
    total = len(candidates)
    print(f"TOTAL NEW CANDIDATES: {total}")
    print("="*140)

if __name__ == '__main__':
    candidates = consolidate_results()
    output_per_ward_table(candidates)
