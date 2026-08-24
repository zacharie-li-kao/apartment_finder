import json

with open("verification_sample.json", "r", encoding="utf-8") as f:
    sample = json.load(f)

print("Sample has these fields:")
if sample:
    print(json.dumps(list(sample[0].keys()), indent=2, ensure_ascii=False))

print(f"\nTotal items: {len(sample)}")
print("\nFirst 3 items:")
for i, item in enumerate(sample[:3]):
    print(f"{i+1}. #{item['number']} {item['name']}")
    # Check if URLs exist
    if "http" in item.get('full_line', ''):
        # Try to extract URL from full_line
        import re
        url_match = re.search(r'href="([^"]+)"', item['full_line'])
        if url_match:
            print(f"   URL: {url_match.group(1)}")
    else:
        print(f"   No URL in sample JSON - need to match from index.html")
