#!/bin/bash
# EXHAUSTIVE SUUMO PAGINATION SCRAPER using curl
# Scrapes all pages for 4 priority wards with proper rate limiting and caching

set -e

WARDS=("sumida" "koto" "katsushika" "itabashi")
BASE_URL="https://suumo.jp/ms/chuko/tokyo"
OUTPUT_FILE="EXHAUSTIVE_CURL_RESULTS.json"

echo "========================================"
echo "EXHAUSTIVE SUUMO PAGINATION SCRAPER"
echo "========================================"
echo "Timestamp: $(date -Iseconds)"
echo "Wards: Sumida, Koto, Katsushika, Itabashi"
echo ""

# Create output file with header
echo "[" > "$OUTPUT_FILE"

total_found=0

for ward in "${WARDS[@]}"; do
    echo "========================================"
    echo "Processing: $ward"
    echo "========================================"

    page=1
    max_pages=50
    consecutive_empty=0

    while [ $page -le $max_pages ] && [ $consecutive_empty -lt 3 ]; do
        url="$BASE_URL/sc_$ward/"
        if [ $page -gt 1 ]; then
            url="$url?page=$page"
        fi

        echo "[Page $page] Fetching: $url"

        # Use curl with appropriate headers
        html=$(curl -s \
            -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
            -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
            -H "Accept-Language: ja,en;q=0.9" \
            -H "Cache-Control: no-cache" \
            --compressed \
            --max-time 30 \
            "$url")

        if [ -z "$html" ]; then
            echo "  [FAIL] Could not fetch page"
            break
        fi

        # Check for no results
        if echo "$html" | grep -q "該当する物件がありません\|物件がありません"; then
            echo "  [END] No results on this page"
            break
        fi

        # Extract property codes from this page
        property_codes=$(echo "$html" | grep -oP 'nc_\K[0-9]+' | sort -u)

        if [ -z "$property_codes" ]; then
            ((consecutive_empty++))
            echo "  [EMPTY] No properties found ($consecutive_empty/3)"
            ((page++))
            sleep 2
            continue
        fi

        consecutive_empty=0
        property_count=$(echo "$property_codes" | wc -l)
        echo "  [FOUND] $property_count properties"

        # Fetch detail pages for each property
        idx=0
        for code in $property_codes; do
            ((idx++))
            detail_url="$BASE_URL/sc_$ward/nc_$code/"

            echo "    [$idx/$property_count] Fetching detail page: nc_$code"

            detail_html=$(curl -s \
                -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
                --max-time 30 \
                "$detail_url")

            if [ ! -z "$detail_html" ]; then
                # Extract property name
                name=$(echo "$detail_html" | grep -oP '<h1[^>]*>\K[^<]+' | head -1)

                # Extract price (万円)
                price=$(echo "$detail_html" | grep -oP '\K[0-9]{2,4}\s*万円' | head -1)

                # Extract size (m²)
                size=$(echo "$detail_html" | grep -oP '\K[0-9]+(?:\.[0-9]+)?\s*m[²²m2]' | head -1)

                # Extract year
                year=$(echo "$detail_html" | grep -oP '(?:19|20)[0-9]{2}\s*年' | head -1)

                # Extract floor
                floor=$(echo "$detail_html" | grep -oP '\K[0-9]+\s*階' | head -1 | sed 's/階.*//')

                # Extract walk time
                walk=$(echo "$detail_html" | grep -oP '\K[0-9]+\s*分' | head -1 | sed 's/分.*//')

                # Extract direction
                direction=$(echo "$detail_html" | grep -oP '(南向き|南|東向き|東|西向き|西|北向き|北|SE|SW|NE|NW|S|E|W|N)' | head -1)

                # Check for freehold
                if echo "$detail_html" | grep -q "所有権"; then
                    ownership="Freehold"
                elif echo "$detail_html" | grep -q "借地権"; then
                    ownership="Leasehold"
                else
                    ownership="Unknown"
                fi

                # Check for vacancy
                if echo "$detail_html" | grep -q "空家\|即入"; then
                    occupancy="Vacant"
                elif echo "$detail_html" | grep -q "オーナーチェンジ"; then
                    occupancy="Tenant"
                else
                    occupancy="Unknown"
                fi

                # Extract fees
                fees=$(echo "$detail_html" | grep -oP '\K[0-9]+(?:,[0-9]+)?\s*円\s*/\s*月' | head -1)

                if [ ! -z "$name" ] && [ ! -z "$price" ]; then
                    echo "      ✓ Found: $name - $price $size"
                    ((total_found++))

                    # Write to JSON (simplified)
                    if [ $total_found -gt 1 ]; then
                        echo "," >> "$OUTPUT_FILE"
                    fi

                    cat >> "$OUTPUT_FILE" << EOF
  {
    "ward": "$ward",
    "name": "$(echo "$name" | sed 's/"/\\"/g')",
    "price": "$price",
    "size": "$size",
    "floor": "$floor",
    "year": "$year",
    "walk": "$walk",
    "station": "N/A",
    "fees": "$fees",
    "direction": "$direction",
    "ownership": "$ownership",
    "occupancy": "$occupancy",
    "url": "$detail_url"
  }
EOF
                fi
            fi

            # Rate limiting
            sleep 0.5
        done

        ((page++))
        # Pause between pages
        sleep 2
    done

    echo ""
done

# Close JSON array
echo "" >> "$OUTPUT_FILE"
echo "]" >> "$OUTPUT_FILE"

echo "========================================"
echo "Complete!"
echo "Total properties found: $total_found"
echo "Output saved to: $OUTPUT_FILE"
echo "========================================"
