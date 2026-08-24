import re

html_file = 'C:\Users\zakat\AppData\Local\Temp\itabashi.html'
with open(html_file, 'r', encoding='utf-8') as f:
    html_content = f.read()

# Find all property links with property codes
property_matches = re.findall(r'nc=(\d+)', html_content)
unique_props = list(set(property_matches))
print(f"Found {len(unique_props)} unique properties")

# Look for property information patterns
# Extract sections with property data
# Properties seem to be in format: <input ... value="01XXXXX" ...> followed by property data

# Try to extract property info by looking for specific data patterns
print("\nTrying to extract property details...")

# Split by property checkbox to isolate each property
props_sections = re.split(r'<input id="bukken_\d+" type="checkbox"', html_content)[1:10]

for i, section in enumerate(props_sections[:3]):
    print(f"\n=== Property {i+1} ===")
    # Look for property name in alt text
    names = re.findall(r'alt="([^"]*)"', section)
    if names:
        print(f"Name: {names[0]}")
    
    # Look for property URLs
    urls = re.findall(r'href="(/ms/chuko/[^"]+)"', section)
    if urls:
        print(f"URL: {urls[0]}")

