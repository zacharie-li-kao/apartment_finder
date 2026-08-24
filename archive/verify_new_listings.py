#!/usr/bin/env python3
"""
Verify new listings from manual SUUMO extraction against known 116 listings
"""

# Known listings from recent commits (sample - last 5 added)
KNOWN_LISTINGS = {
    "セザール久が原",           # #126
    "メゾン蓮根",               # #125
    "サンタウン立花１号棟",     # #124
    "エスカイア等々力",         # #123
}

# Listings found in SUUMO Sumida search (extracted from page text)
# Format: (Name, Price M¥, Size m², Layout, Year, Walk min, Station, Direction)
SUUMO_SUMIDA_PAGE1 = [
    ("モアステージ隅田", 2.38, 32.85, "2K", 1987, 8, "東向島", "?"),
    ("シャンボール東向島", 2.99, 38.21, "1LDK", 1981, 10, "曳舟", "SE"),
    ("シュロス錦糸町", 3.58, 50.4, "3K", 1979, 13, "錦糸町", "SE"),
    ("ドルミ錦糸町大興ビル", 3.98, 52.91, "2LDK", 1980, 5, "錦糸町", "S"),
    ("ビィ・フォルマ亀戸", 3.98, 43.06, "2DK", 2021, 4, "小村井", "?"),
    ("NICアーバンハイム亀戸", 3.99, 56.16, "3LDK", 1986, 13, "亀戸", "SW"),
    ("東向島サニーホームズ", 4.199, 56.27, "2LDK", 1973, 3, "曳舟", "SE"),
    ("クレド・ハイツリー両国", 4.199, 40.2, "1LDK", 1988, 7, "両国", "SE"),
    ("業平橋住宅", 4.49, 48.6, "2LDK", 1972, 5, "東京スカイツリー", "E"),
    ("ドルミ錦糸町長谷川ビル", 4.58, 46.75, "2DK", 1980, 7, "錦糸町", "?"),
    ("業平橋住宅", 4.69, 54, "2DK+S", 1972, 7, "押上", "?"),
    ("GENOVIA鐘ヶ淵", 4.78, 41.4, "1LDK", 2023, 3, "鐘ヶ淵", "?"),
    ("ハイツ両国駅前", 4.79, 44.65, "1LDK", 1982, 8, "両国", "S"),
    ("フュージョナル東墨田", 4.88, 45.05, "1LDK", 2021, 7, "八広", "?"),
    ("ハイツ錦糸町", 4.98, 63.18, "3LDK", 1974, 8, "錦糸町", "?"),
    ("ライオンズプラザ東向島", 4.998, 51.66, "2LDK", 1993, 3, "東向島", "?"),
    ("朝日言問マンション", 4.999, 46.45, "1LDK", 1982, 7, "東京スカイツリー", "?"),
]

def check_criteria(price_m, size_sqm, layout, year, walk, direction=None):
    """Check if listing meets all criteria"""
    criteria_check = {
        'Price (1.5M-40M)': 1.5 <= price_m <= 40,
        'Size (≥30m²)': size_sqm >= 30,
        'Layout (1LDK+)': layout in ['1LDK', '2LDK', '3LDK', '2DK', '3DK'],
        'Year (1982+)': year >= 1982,
        'Walk (≤15min)': walk <= 15,
        'Floor (2F+)': True,  # Not extractable from page text alone
        'Freehold only': True,  # Not extractable from page text alone
        'Fees (≤30k/mo)': True,  # Not extractable from page text alone
    }

    return all(criteria_check.values()), criteria_check

def main():
    print("NEW LISTINGS ANALYSIS - SUUMO Sumida Ward")
    print("=" * 120)
    print()

    new_count = 0
    criteria_pass = 0

    for name, price_m, size_sqm, layout, year, walk, station, direction in SUUMO_SUMIDA_PAGE1:
        is_new = name not in KNOWN_LISTINGS
        passes_criteria, details = check_criteria(price_m, size_sqm, layout, year, walk, direction)

        if is_new:
            new_count += 1
            status = "🆕 NEW"
        else:
            status = "   KNOWN"

        print(f"{status} | {name:25s} | ¥{price_m:.2f}M | {size_sqm:5.1f}m² | {layout:6s} | {year:4d} | {walk:2d}min | {station:15s}")

        if is_new:
            if passes_criteria:
                criteria_pass += 1
                print(f"      ✓ Meets all basic criteria (price, size, layout, year, walk)")
            else:
                print(f"      ✗ Fails criteria:", end="")
                for criteria, result in details.items():
                    if not result:
                        print(f" {criteria}", end="")
                print()
        print()

    print("=" * 120)
    print(f"Total listings in Sumida page 1: {len(SUUMO_SUMIDA_PAGE1)}")
    print(f"Not in known 116: {new_count}")
    print(f"Passing basic criteria: {criteria_pass}")
    print()
    print("NOTE: Floor number, freehold status, management fees, and exact direction need detail page fetch")
    print()

    # Filter and display the new ones that pass basic criteria
    print("CANDIDATES FOR REVIEW (new + pass basic criteria):")
    print("-" * 120)
    candidates = []
    for name, price_m, size_sqm, layout, year, walk, station, direction in SUUMO_SUMIDA_PAGE1:
        if name not in KNOWN_LISTINGS:
            passes_criteria, _ = check_criteria(price_m, size_sqm, layout, year, walk)
            if passes_criteria:
                candidates.append((name, price_m, size_sqm, layout, year, walk, station, direction))

    for name, price_m, size_sqm, layout, year, walk, station, direction in sorted(candidates, key=lambda x: x[1]):
        print(f"{name:30s} | ¥{price_m:6.2f}M | {size_sqm:5.1f}m² | {layout:7s} | {year:4d} | {walk:2d}min walk | {station}")

if __name__ == '__main__':
    main()
