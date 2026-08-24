#!/usr/bin/env python3
"""Extract all known property names from git commit history."""

import json
import re
import subprocess
from pathlib import Path

def extract_properties():
    """Extract all property names from git log."""

    # Get full git log
    result = subprocess.run(
        ["git", "log", "--format=%B"],
        capture_output=True,
        encoding='utf-8',
        cwd="/Users/zakat/Desktop/apartment" if Path("/Users/zakat").exists() else "C:\\Users\\zakat\\Desktop\\apartment"
    )

    if result.returncode != 0:
        print("Error running git log")
        return []

    log_text = result.stdout

    # Extract properties from "Add #" lines
    # Pattern: "Add #XXX PropertyName (details)"
    add_pattern = r'^Add #[\d-]+ ([^\n\(]+)'

    properties = []
    for line in log_text.split('\n'):
        if line.startswith('Add #'):
            match = re.search(add_pattern, line)
            if match:
                prop_name = match.group(1).strip()
                # Clean up
                prop_name = prop_name.replace(' + ', '|').split('|')[0].strip()
                prop_name = re.sub(r'\s+', ' ', prop_name)
                if prop_name and len(prop_name) > 2:
                    properties.append(prop_name)

    # Also extract from the "Existing Database" commit
    db_pattern = r'#(\d+)[):]?\s+([^\n\—•|]+(?:マンション|コーポ|パーク|ハイツ|ホームズ|タウン|プラザ|ガーデン|カエサル|ライオン|ダイヤ|エスカ|メゾン|セザール|グリーン|スカイ|ランド|ラブリ|ルック|サンデュ|エクレール|エスペランサ|朝日|東|ライオンズ|リーベスト|Sevenstar|シティ|Heights|パークサイド|東白|ガーデンプラザ|クイーンズ|バイ|キャピタル|第|の|塔|Palacio|Vista|Grand)[^\n]*)'

    for match in re.finditer(db_pattern, log_text, re.MULTILINE):
        try:
            number = match.group(1)
            name = match.group(2).strip()
            # Clean up
            name = name.split('—')[0].split('•')[0].split('|')[0].strip()
            name = name.strip('·')
            if name and len(name) > 2:
                properties.append(name)
        except:
            pass

    # Also handle multi-property lines like:
    # "Add #96-100: 向島ダイヤモンド+ランドステージ+東大島ハイライズ+ルックハイツ両国+ラブリハイツ亀戸"
    multi_pattern = r'([\w\d]+(?:マンション|コーポ|パーク|ハイツ|ホームズ|タウン|プラザ|ガーデン|カエサル|ライオン|ダイヤ|エスカ|メゾン|セザール|グリーン|スカイ|ランド|ラブリ|ルック|サンデュ|エクレール|エスペランサ|朝日|東|ライオンズ|リーベスト|Sevenstar|シティ|Heights|パークサイド|東白|ガーデンプラザ|クイーンズ|第|バイ|キャピタル|Palacio|Vista|Grand)[^\n+—•|]*)'

    for match in re.finditer(multi_pattern, log_text):
        name = match.group(1).strip()
        if name and len(name) > 2 and name not in ['Add', 'Katsushika']:
            properties.append(name)

    # Deduplicate and clean
    unique_props = set()
    for prop in properties:
        prop = prop.replace('⭐⭐', '').replace('⭐', '').strip()
        prop = re.sub(r'\s+', ' ', prop)
        prop = prop.strip('·')
        if prop and len(prop) > 2 and not prop.startswith('count'):
            unique_props.add(prop)

    return sorted(list(unique_props))

def main():
    # Extract properties
    properties = extract_properties()

    # Build JSON structure
    data = [{"name": prop, "added": True} for prop in properties]

    # Save to file
    output_file = Path("KNOWN_LISTINGS.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(properties)} unique properties")
    print(f"Saved to {output_file}")

    # Show sample
    if properties:
        print(f"\nSample (first 20):")
        for prop in properties[:20]:
            print(f"  - {prop}")

if __name__ == "__main__":
    main()
