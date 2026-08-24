#!/bin/bash
# Exhaustive paced SUUMO crawler for Itabashi & Kita
# Uses curl with 5-second sleep between ALL requests

SCRATCHPAD="C:\Users\zakat\AppData\Local\Temp\claude\C--Users-zakat-Desktop-apartment\01721473-cadc-4daf-b4ad-0ffbd713cc1c\scratchpad"
OUTPUT_DIR="."
WARDS="itabashi kita"
BASE_URL="https://suumo.jp/ms/chuko/tokyo/sc_"
DETAIL_URL="https://suumo.jp/ms/chuko/tokyo/sc_"

# Create temp directories
mkdir -p "$SCRATCHPAD/listings" "$SCRATCHPAD/details"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Headers to mimic browser
HEADERS=(
    -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    -H "Accept-Language: ja,en;q=0.9"
    -H "Connection: keep-alive"
)

for ward in $WARDS; do
    log "=========================================="
    log "Starting $ward exhaustive search..."
    log "=========================================="

    page=1
    total_found=0
    new_on_page=0

    # Store property codes seen to avoid duplicates
    > "$SCRATCHPAD/${ward}_codes.txt"

    while true; do
        if [ $page -eq 1 ]; then
            url="${BASE_URL}${ward}/"
        else
            url="${BASE_URL}${ward}/?page=${page}"
        fi

        log "Fetching page $page for $ward: $url"
        curl_output="$SCRATCHPAD/listings/${ward}_page_${page}.html"

        # Fetch with timeout and retries
        max_retries=3
        retry=0
        while [ $retry -lt $max_retries ]; do
            http_code=$(curl -s -w "%{http_code}" "${HEADERS[@]}" \
                --max-time 15 \
                -o "$curl_output" \
                "$url" 2>&1)

            if [ "$http_code" = "200" ]; then
                log "✓ Page $page fetched (HTTP 200)"
                break
            elif [ "$http_code" = "429" ] || [ "$http_code" = "503" ]; then
                retry=$((retry + 1))
                wait_time=$((5 ** retry))
                log "⚠ Got HTTP $http_code. Waiting ${wait_time}s before retry $retry/$max_retries"
                sleep $wait_time
            else
                log "✗ Got HTTP $http_code"
                break
            fi
        done

        # Extract property codes with grep
        codes=$(grep -oP 'nc=\d+' "$curl_output" | cut -d'=' -f2 | sort -u)

        if [ -z "$codes" ]; then
            log "No properties found on page $page. Ending pagination."
            break
        fi

        new_count=0
        for code in $codes; do
            if ! grep -q "^${code}$" "$SCRATCHPAD/${ward}_codes.txt"; then
                echo "$code" >> "$SCRATCHPAD/${ward}_codes.txt"
                new_count=$((new_count + 1))
            fi
        done

        total_found=$((total_found + new_count))
        log "Page $page: $new_count new properties (cumulative: $total_found)"

        # If no new properties, end pagination
        if [ $new_count -eq 0 ]; then
            log "No new properties on page $page. Pagination complete."
            break
        fi

        page=$((page + 1))
        log "Waiting 5s before next page fetch..."
        sleep 5
    done

    log "=========================================="
    log "$ward: Found $total_found total unique properties"
    log "Starting detail-page fetch (only 1982+)..."
    log "=========================================="

    # Read all codes and fetch details (only 1982+)
    processed=0
    while IFS= read -r code; do
        detail_url="${DETAIL_URL}${ward}/nc_${code}/"
        detail_output="$SCRATCHPAD/details/${ward}_${code}.html"

        log "Fetching detail [$((++processed))]: $code"

        max_retries=2
        retry=0
        while [ $retry -lt $max_retries ]; do
            http_code=$(curl -s -w "%{http_code}" "${HEADERS[@]}" \
                --max-time 15 \
                -o "$detail_output" \
                "$detail_url" 2>&1)

            if [ "$http_code" = "200" ]; then
                # Extract year to filter pre-1982
                year=$(grep -oP '\d{4}年' "$detail_output" | head -1 | grep -oP '\d{4}')
                if [ -n "$year" ] && [ "$year" -ge 1982 ]; then
                    log "  ✓ Year: $year (1982+) - keep"
                else
                    log "  ✗ Year: ${year:-N/A} (pre-1982 or missing) - skip"
                fi
                break
            elif [ "$http_code" = "429" ] || [ "$http_code" = "503" ]; then
                retry=$((retry + 1))
                wait_time=$((3 ** retry))
                log "  ⚠ Got HTTP $http_code. Waiting ${wait_time}s"
                sleep $wait_time
            else
                log "  ✗ Got HTTP $http_code"
                break
            fi
        done

        log "Waiting 5s before next detail fetch..."
        sleep 5

    done < "$SCRATCHPAD/${ward}_codes.txt"

done

log "=========================================="
log "Crawler complete. Results in $SCRATCHPAD"
log "=========================================="
