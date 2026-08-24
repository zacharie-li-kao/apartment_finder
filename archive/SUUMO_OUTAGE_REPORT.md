# SUUMO Search Outage Report
**Date:** 2026-06-30  
**Time:** 12:17 UTC (JST 21:17)

## Status Summary

**SUUMO is currently completely unavailable due to infrastructure outage/heavy load.**

All access attempts across three wards (Nerima, Setagaya, Taito) return HTTP 503 errors:
- Browser access: Error pages with "ページを表示できません。ただいま大変混み合っております。"
- curl/programmatic access: Consistent 503 responses
- Python scraper with retry/backoff: All retries exhausted with 503

## Attempted Access Methods

1. **curl with standard headers** (12:17): 503 ✗
2. **curl with browser User-Agent** (12:17): 503 ✗
3. **Chrome browser navigation** (12:17-12:30): Error pages, 503 ✗
4. **Python requests with retry/backoff** (12:17): 3 retries × 3 wards all failed ✗

## Alternative Portals Status

- **AtHome (athome.co.jp)**: URL routing issues, showing 404-style errors
- **Yahoo Real Estate (realestate.yahoo.co.jp)**: Redirects to AtHome
- **Mitsui Rehouse (rehouse.co.jp)**: Loading but shows regional filters, not exhaustive search
- **HOMES.co.jp**: Not attempted (noted in memory as AWS WAF-blocked)

## What Was Prepared

A comprehensive Python scraper (`suumo_scraper.py`) was created with:

### Features:
- ✓ Exhaustive pagination through all pages for each ward
- ✓ Property code extraction and deduplication (nc=XXXXX)
- ✓ Detail page fetching for all properties
- ✓ Extraction of all required fields:
  - Price, size, floor, year, walk time, station, layout, direction, monthly fees
  - Ownership type (freehold vs. leasehold)
  - Vacancy status and renovation flags
  
### Hard Filter Implementation:
- ✓ Year ≥1982 (新耐震基準)
- ✓ Price ≤¥40M
- ✓ Size ≥30m²
- ✓ Layout ≥1LDK
- ✓ Floor ≥2F (no ground floor)
- ✓ Walk ≤15 min to station
- ✓ Monthly fees ≤¥30k/month
- ✓ Freehold only (所有権)
- ✓ No north-facing only (北向き)

### Output Format:
Tab-separated with columns:
```
NAME|PRICE|SIZE|FLOOR|YEAR|WALK|STATION|FEES|LAYOUT|DIRECTION|URL
```

Both qualified properties and disqualification reasons are logged.

### Rate Limiting & Recovery:
- Exponential backoff (1s, 2s, 4s) for 503 errors
- 1-second delay between detail page requests
- 2-second delay between pagination pages
- 3 retry attempts with configurable backoff multiplier

## Next Steps

### Immediate (Once SUUMO Recovers)
1. Run the scraper immediately:
   ```bash
   python suumo_scraper.py
   ```
2. Results will be saved to:
   - `SUUMO_RESULTS_FULL.txt` (human-readable)
   - `SUUMO_RESULTS.json` (for processing)

### Long-Term (Automated Monitoring)
A recurring task can be scheduled to:
- Check SUUMO status every 30 minutes
- Auto-run scraper when SUUMO responds with 200 OK
- Alert when results change

### Contingency Strategies
If SUUMO remains unavailable:
1. **Use AtHome (athome.co.jp)** - largest alternative portal
   - Similar filtering capabilities
   - Different property IDs, may have exclusive listings
   
2. **Use Yahoo Real Estate (realestate.yahoo.co.jp)**
   - Aggregates from multiple sources including SUUMO
   - Good for cross-checking prices
   
3. **Use agency-direct sites:**
   - Mitsui Rehouse (rehouse.co.jp)
   - Tokyu Livable (livable.co.jp)
   - Sumitomo Realty (stepon.co.jp)
   - May have exclusive pre-sales

## Wards to Search

When SUUMO recovers:
1. **Nerima-ku (練馬区)** - Lower priority but acceptable if strong value
2. **Setagaya-ku (世田谷区)** - Standard ward, likely high prices
3. **Taito-ku (台東区)** - Near Skytree area, good access

## Existing Data

File: `SUUMO_RESULTS.txt`
- Contains partial results from Itabashi and Taito (from prior session)
- Mostly disqualifications due to year, price, and floor criteria
- Provides baseline for comparison when new search completes

---

**Status:** AWAITING SUUMO RECOVERY  
**Last Check:** 2026-06-30 12:17 UTC  
**Next Retry:** Manual (can be automated via scheduled task)
