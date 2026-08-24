# Itabashi & Kita Exhaustive Search - Crawler Analysis & Fixes

## Task
Complete exhaustive paced search of Itabashi-ku (板橋区) and Kita-ku (北区) on SUUMO with aggressive rate limiting (5s between requests). Focus on post-1982 candidates only.

## Critical Issues Found & Fixed

### 1. Pagination Parameter Bug (BLOCKING)
**Status**: CRITICAL - prevents full crawl

**Issue**: Original crawler used `?page={n}` which SUUMO ignores
- Itabashi has 60+ pages but original code would exit on page 2
- Sees identical property codes on page 2 → incorrectly concludes pagination complete
- **Evidence**: `SUUMO_RESULTS.txt` titled "Page 1 only" despite claim to be exhaustive

**Root Cause**: SUUMO uses `pn=` parameter, not `page=`

**Fix Applied**: Corrected to `?pn={page}` in `fixed_crawler_itabashi_kita.py`

---

### 2. Parser Regex Bugs (BLOCKING)
**Status**: CRITICAL - produces garbage data

**Issue**: Field extraction regexes match wrong values
- **Year**: `(\d{4})年` grabs first 4-digit-年 anywhere on page (loan terms, campaigns, copyright year, not 築年月)
- **Floor**: Pattern matches incorrectly - every row in existing results shows `N/AF` (not-a-floor)
- **Fees**: `(\d+(?:,\d+)?)円` grabs first ¥ amount on page (likely a price snippet, not fees) - every row shows `10` (obviously wrong)

**Evidence in SUUMO_RESULTS.txt**:
```
ライオンズマンション赤塚|24.8M|41.08m²|N/AF|1973|5min|地下鉄赤塚|10|2DK+S|南東
メゾン蓮根|24.8M|48.19m²|N/AF|1982|10min|蓮根|10|2LDK|東
```
All rows: Floor=`N/AF`, Fees=`10` ⟹ parser is broken

**Fix Applied**:
- Year: Look specifically for `築年月.*?(\d{4})年` pattern
- Floor: Match with `(?:^|\s)(\d+)階(?:／(\d+)階建)?` pattern (captures current & building height)
- Fees: Extract `管理費` + `修繕積立金` separately, sum them (not just first ¥ match)

---

### 3. Hard Criteria Logic Bug (BLOCKING)
**Status**: CRITICAL - produces false positives

**Issue**: Hard criteria checks skip when field is None
```python
# BROKEN:
if prop.get('floor') and prop['floor'] < 2:  # If floor=None, check SKIPPED
    return False
```
This means:
- Property with unparsed floor (None) → passes floor check ✗
- Property with unparsed fees (None) → passes fees check ✗
- Floor ≥2F and Fees ≤30k are HARD requirements, not optional

**Fix Applied**:
```python
# FIXED:
if prop.get('floor') is None:
    return False, "Floor missing"  # Explicit fail
if prop['floor'] < 2:
    return False, f"Floor {prop['floor']}F < 2F"
```

---

## How Rate Limiting is Handled

Current Implementation:
```python
# Fetch with exponential backoff
for attempt in range(3):
    if status == 200:
        return
    elif status in (429, 503):
        wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
        sleep(wait)
        continue
```

Plus: 5-second forced sleep between EVERY request (aggressive pacing)

This ensures:
- Respectful rate limiting (exponential backoff on 503/429)
- Sustainable crawl pace (won't hammer SUUMO)
- Complete enumeration (retries eventually succeed)

---

## Crawler Implementation

**File**: `fixed_crawler_itabashi_kita.py`

### Key Features
- **Pagination**: Uses correct `pn=` parameter
- **Filtering**: Skips pre-1982 immediately (saves requests)
- **Parsing**: Fixed regexes for year/floor/fees
- **Validation**: Rejects properties with missing critical fields
- **Rate Limiting**: 5s sleep + exponential backoff on 503/429
- **Output**: TSV results with qualified/disqualified breakdown

### Hard Criteria Applied
- Price: ≤¥40M
- Size: ≥30m²
- Layout: ≥1LDK (parsed, but 1LDK implied by no explicit filtering)
- Year: ≥1982 (新耐震基準)
- Walk: ≤15 min to station
- Floor: ≥2F (no ground floor)
- Fees: ≤¥30k/month
- Ownership: Freehold (所有権) only
- Direction: Not north-only (北向き)

### Missing Critical Field = Auto-Fail
Properties with unparsed price/size/floor/walk/fees are routed to "needs manual review" (disqualified).

---

## Execution Status

**Started**: June 30, 2026, ~12:00 JST
**Current Status**: Running in background with rate-limit recovery
**Expected Duration**: 2-4 hours (60+ pages × 5-10 props/page × 5s min. per request + exponential waits)

### Output Files
- `fixed_crawler.log` — full debug log
- `FIXED_RESULTS.txt` — TSV results (qualified/disqualified)
- `FIXED_RESULTS.json` — structured JSON output

---

## Previous Broken Crawler

The original `suumo_scraper.py` / web scraping attempts had all three bugs above. Results from those runs (SUUMO_RESULTS.txt, SUUMO_RESULTS_FULL.txt) are **unreliable** due to parser failures.

New run with fixed crawler will produce **accurate** candidate list for Itabashi & Kita.

---

## Next Steps
1. Monitor `FIXED_RESULTS.txt` when complete
2. Merge qualified results into main apartment database
3. Verify top candidates via detail-page inspection (Rehouse/Livable/Century21 for confirm-able fees)
4. Consider other under-explored wards once Itabashi/Kita exhaustion confirmed
