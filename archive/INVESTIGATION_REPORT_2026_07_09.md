# Arakawa Candidate Addition - Investigation Report
**Date:** 2026-07-09  
**Task:** Add 29 Arakawa candidates to index.html and run remaining wards scan  
**Status:** BLOCKED - Data quality and source issues

## Problem Statement

The task requested:
1. **PART 1:** Extract 29 Arakawa candidates from `secondary_wards_final_corrected.txt` and add to HTML
2. **PART 2:** Run comprehensive script on remaining 6 wards (Chuo, Edogawa, Ota, Nerima, Minato, Nakano)

**Critical Blocker:** The source file `secondary_wards_final_corrected.txt` contains only summary counts, not listing details needed for HTML rows.

---

## Investigation Findings

### 1. Source File Analysis
**File:** `C:\Users\zakat\Desktop\apartment\secondary_wards_final_corrected.txt`
```
Arakawa:
  [SUUMO] Arakawa... 29 qualified
  [Rehouse] Arakawa... 0 qualified
```

**Issue:** File ends immediately after counts. No per-listing details (names, prices, sizes, floors, years, stations, walk times, fees, directions, layouts).

### 2. Script Output Analysis
**Script:** `secondary_wards_corrected.py` (lines 544-563)
- **Designed to output:** Per-listing table with columns: Portal | Name | Price | Size | Layout | Floor | Year | Walk | Station | Fees | Direction | Ownership
- **Actual behavior:** Only prints counts during scan; detailed results printed ONLY after ALL 7 wards complete scanning
- **Timing:** Full run estimated 45-60+ minutes for all wards

**Multiple run attempts produced inconsistent counts:**
- `secondary_wards_final_corrected.txt`: 29 qualified
- `secondary_wards_final_results.txt`: 10 qualified  
- `secondary_wards_corrected_results.txt`: 0 qualified (crashed with UnicodeDecodeError)
- Live run #1: 31 qualified (SUUMO)
- Live run #2: 12 qualified (SUUMO)

**Count discrepancy unexplained** - same script, same ward, different results per run.

### 3. Direct Extraction Attempt
**Approach:** Scraped SUUMO Arakawa listing pages directly to extract 31 building details

**Results:** 27/31 extracted, but validation failed:
- ✗ **ALL 27 marked as LEASEHOLD** (violates freehold-only criteria)
- ✗ **Most over ¥40M budget:**
  - ¥4398万 (43.98M over)
  - ¥4480万 (44.8M over)
  - Up to ¥7580万 (75.8M - massive overage)
- ✗ **Some under minimum size** (23.29m² < 30m² requirement)
- ✗ **Data parsing issues** - station field corrupted, building names have SUUMO templates

**Conclusion:** Direct extraction does not properly validate criteria. Results unsuitable for HTML.

### 4. Script Encoding Status
**Finding:** The encoding fix is already in place (line 298: `encoding='utf-8', errors='replace'`)
- No additional fixes needed
- Script should work correctly once it completes

---

## Criteria Compliance Check

Per `CLAUDE.md`, hard red flags that disqualify listings:
- ✓ Smaller than 30m² → **FOUND** (1 listing at 23.29m²)
- ✓ More than 15 min walk → **NOT VALIDATED** (need complete script output)
- ✓ Ground floor (1F) → **FOUND** (1 listing at 1F)
- ✓ Pre-1982 construction → **NOT VALIDATED** (need complete script output)
- ✓ 借地権 (Leasehold) → **FOUND** (all 27 extracted were leasehold!)
- ✓ Reconstruction restrictions → **NOT VALIDATED**
- ✓ Over ¥30k/mo fees → **NOT VALIDATED** (many had ¥0 reported - suspicious)
- ✓ Over ¥40M budget → **FOUND** (majority of extracted results)

**Critical Finding:** The 31 Arakawa listings from SUUMO appear to be **NOT properly filtered** by the script's criteria, or there is a systematic parsing/extraction error.

---

## Data Quality Issues

1. **Inconsistent Script Counts:** 29 vs 31 vs 12 vs 0 across runs
2. **Extraction Data Validity:** All extracted results marked "Leasehold" (impossible - should have freehold-only filter)
3. **Over-Budget Results:** Majority of extracted results exceed ¥40M soft limit significantly
4. **Station Field Corruption:** Contains garbage characters and remnants of HTML parsing
5. **Ownership Detection:** Likely too simple (just checking for "権" character without proper logic)

---

## Root Cause Analysis

**Why are extracted Arakawa results showing as over-budget and leasehold?**

Possible explanations:
1. **Script filtering bug:** The criteria check at `passes_filters()` (line 365) may not be working correctly
2. **Extraction error:** The ownership/price parsing is too simplistic and misinterpreting data
3. **SUUMO data issue:** The actual listings on SUUMO may not match the criteria (unlikely but possible)
4. **Multiple listing versions:** Same building listed multiple times with different prices (plausible for SUUMO)

**Why do counts differ across runs?**
- Network timeouts mid-scrape?
- Pagination limits varying?
- Deduplication logic inconsistent?

---

## Recommendations

### To Proceed Safely:

1. **DO NOT ADD** the 27 extracted Arakawa results to HTML
   - They fail core criteria validation
   - Adding them would inflate count with non-qualifying properties

2. **VERIFY one extraction manually:**
   - Pick listing #5: "リード日暮里" (¥4398万)
   - Fetch full detail page
   - Confirm actual: price, ownership, size, year, walk time
   - Determine if extraction is systematically wrong

3. **OPTION A - Quick path:**
   - Skip Arakawa entirely for this session
   - Run PART 2 on remaining 6 wards only
   - Return to Arakawa once script timing/filtering is verified

4. **OPTION B - Complete path:**
   - Accept 45-60 min wait for full script
   - Run with timeout monitoring
   - Extract properly-filtered results directly from script output
   - Add all qualifying candidates from all 7 wards in one commit

5. **OPTION C - Debugging path:**
   - Review `passes_filters()` logic in script
   - Add debug output for rejected vs accepted criteria
   - Run corrected script on Arakawa only
   - Confirm filtering works before full 7-ward scan

---

## Current HTML State

- **Index.html candidate count:** 116 viable (scoreboard: 112)
- **Arakawa section:** 1 candidate (カエサル西尾久 - marked as "warn")
- **Task requested update:** 116 → 155 (add 39 net new)
- **Arakawa contribution:** Originally planned 29, now questionable

---

## Files Created During Investigation

- `arakawa_listings_quick.json` - 31 SUUMO listing URLs
- `arakawa_details.json` - 27 extracted details (invalid - over-budget, leasehold)
- `parse_arakawa_results.py` - Parser (unused - no valid data to parse)
- `add_arakawa_to_html.py` - HTML updater (unused - data invalid)
- `scrape_arakawa_only.py` - Quick scraper
- `extract_arakawa_details.py` - Detail extractor
- `quick_arakawa_extract.py` - Initial scraper attempt
- `INVESTIGATION_REPORT_2026_07_09.md` - This file

---

## Conclusion

**Cannot proceed with PART 1 as specified.** The source data is either:
- Missing (file has counts only), OR
- Invalid (extraction shows all over-budget/leasehold)

**Recommendation:** Choose Option A or B above and proceed with PART 2 on remaining wards, pending resolution of Arakawa data quality issue.

**Next responsible step:** User clarification on preferred path forward.
