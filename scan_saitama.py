#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Saitama detached-house scanner -> saitama_db.json

Separate from the Tokyo apartment pipeline (db.json / index.html are not touched).
Scrapes SUUMO 中古一戸建て for the core cities near the Arakawa, paginates each
city list, fetches each new detail page once, and scores against the house
criteria.  Reuses scan.get (503 backoff) and scan.txt (HTML to text).
"""
import json, os, re, sys, time, random, unicodedata
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scan  # noqa: E402  (importing is side-effect free: main() is guarded)

DB = os.path.join(HERE, "saitama_db.json")
JST = timezone(timedelta(hours=9))
BASE = "https://suumo.jp/chukoikkodate/saitama/{sc}/"

# slug -> (name, station-quality bonus, note)
CITIES = {
    "sc_saitamashiurawa":  ("Saitama-Urawa", 3),
    "sc_saitamashiomiya":  ("Saitama-Omiya", 3),
    "sc_saitamashiminami": ("Saitama-Minami", 2),
    "sc_saitamashiminuma": ("Saitama-Minuma", 2),
    "sc_kawaguchi":        ("Kawaguchi", 2),
    "sc_warabi":           ("Warabi", 2),
    "sc_toda":             ("Toda", 2),
    "sc_ageo":             ("Ageo", 1),
    # Tokyo-edge cities with fast links (added on request)
    "sc_kawagoe":          ("Kawagoe", 2),
    "sc_wako":             ("Wako", 2),
    "sc_shiki":            ("Shiki", 2),
    "sc_niiza":            ("Niiza", 1),
    "sc_asaka":            ("Asaka", 1),
}

PRICE_CAP = 4000        # 万円
WALK_CAP = 15           # minutes to nearest station
# Very close to central Tokyo: a 20-minute walk to the station is acceptable
NEAR_TOKYO = {"Kawaguchi", "Warabi", "Toda", "Wako", "Asaka"}
NEAR_TOKYO_WALK_CAP = 20
MIN_YEAR = 1982

# station lines/stations that matter to the user (bonus, not a filter)
GOOD_STATIONS = {"大宮": 3, "浦和": 3, "西川口": 2, "川口": 2, "蕨": 2, "戸田": 2,
                 "南浦和": 2, "与野": 2, "北浦和": 2, "東浦和": 1, "上尾": 1,
                 "川越": 2, "和光市": 2, "志木": 2, "新座": 1, "朝霞": 1}


def collect_ids(slug):
    """Walk every page of one city list until a page adds no new listing."""
    seen, out = set(), []
    for page in range(1, 60):
        url = BASE.format(sc=slug) + (f"?page={page}" if page > 1 else "")
        page_html = scan.get(url)
        if not page_html:
            print(f"  {slug} p{page}: fetch failed ({scan.LAST_ERROR}); stopping city")
            break
        found = re.findall(r"/chukoikkodate/saitama/%s/(nc_\d+)/" % re.escape(slug), page_html)
        new = [i for i in dict.fromkeys(found) if i not in seen]
        if not new:
            break
        seen.update(new)
        out.extend(new)
        time.sleep(random.uniform(0.6, 1.2))
    return out


def field(t, label, pat=r"(\S+)"):
    m = re.search(re.escape(label) + r" ヒント " + pat, t)
    return m.group(1) if m else ""


def parse_detail(url, slug, nc):
    raw = scan.get(url)
    if not raw:
        return None
    t = unicodedata.normalize("NFKC", scan.txt(raw))  # １種 -> 1種, ＪＲ -> JR
    rec = {"id": nc, "url": url, "city": CITIES[slug][0], "slug": slug}

    m = re.search(r"価格更新お知らせメール.*?(\d[\d,\.]*)\s*(万円|億円?)", t)
    if m:
        v = float(m.group(1).replace(",", ""))
        rec["price_man"] = v * (10000 if m.group(2).startswith("億") else 1)
    m = re.search(r'(埼玉県[^\s\[",]+)', t)
    rec["address"] = m.group(1) if m else ""
    m = re.search(r"交通 (.*?)\s*\[", t)
    rec["transport"] = m.group(1) if m else ""
    m = re.search(r"土地面積\s*ヒント\s*([\d.]+)m", t)
    rec["land_m2"] = float(m.group(1)) if m else None
    m = re.search(r"建物面積\s*ヒント\s*([\d.]+)m", t)
    rec["building_m2"] = float(m.group(1)) if m else None
    rec["layout"] = field(t, "間取り")
    rec["zoning"] = field(t, "用途地域", r"(\S+)")
    rec["rights"] = field(t, "土地の権利形態")
    m = re.search(r"完成時期\(?築年月\)?\s*ヒント\s*(\d{4})年", t)
    rec["built_year"] = int(m.group(1)) if m else None
    m = re.search(r"私道負担・道路\s*ヒント\s*(.*?)\s*(?:完成時期|住所)", t)
    rec["road"] = m.group(1) if m else ""
    m = re.search(r"その他概要・特記事項\s*(.{0,400})", t)
    rec["remarks"] = m.group(1) if m else ""
    m = re.search(r"建ぺい率・容積率\s*ヒント\s*(\d+)％・(\d+)％", t)
    rec["coverage"] = f"{m.group(1)}%/{m.group(2)}%" if m else ""
    rec["fetched"] = datetime.now(JST).isoformat(timespec="minutes")
    return rec


def walk_info(transport):
    """Nearest walk-only station (ignores bus-then-walk routes)."""
    best = None
    for entry in transport.split("[ 乗り換え案内 ]"):
        if "バス" in entry:
            continue
        m = re.search(r"([^\s「]*)「([^」]+)」\s*歩(\d+)分", entry)
        if m:
            line, station, mins = m.group(1), m.group(2), int(m.group(3))
            if best is None or mins < best[2]:
                best = (line, station, mins)
    return best


def evaluate(r):
    """Hard rejects, soft concerns and a score. Returns (verdict, reasons, score)."""
    rej, warn, score = [], [], 0.0
    p = r.get("price_man")
    if p is None:
        warn.append("price unknown")
    elif p > PRICE_CAP:
        rej.append(f"price {p:.0f}万 over 4000万")
    y = r.get("built_year")
    if y is None:
        warn.append("build year unknown")
    elif y < MIN_YEAR:
        rej.append(f"built {y} (pre-1982)")
    # We need to own the land AND the house. Unstated rights count as a reject.
    rights = r.get("rights", "")
    if "所有権" not in rights:
        rej.append(f"land rights not 所有権 ({rights or 'not stated'})")
    if re.search(r"借地|底地|地上権|定期借地", r.get("remarks", "") + " " + r.get("road", "")):
        rej.append("借地/底地 mentioned in remarks")
    text = r.get("remarks", "") + " " + r.get("road", "")
    if "再建築不可" in text:
        rej.append("再建築不可")
    if "アスベスト" in text:
        warn.append("asbestos mentioned — check")
    walk = walk_info(r.get("transport", ""))
    r["walk"] = walk
    if walk is None:
        warn.append("no walk-only station time")
    cap = NEAR_TOKYO_WALK_CAP if r.get("city") in NEAR_TOKYO else WALK_CAP
    if walk is None:
        pass  # already flagged above
    elif walk[2] > cap:
        rej.append(f"walk {walk[2]} min to {walk[1]} (cap {cap})")
    if r.get("road") and "私道" in r["road"] and "無" not in r["road"][:2]:
        warn.append("私道 (private road) — check")
    zone = r.get("zoning", "")
    if "低層" in zone:
        score += 3; r["calm"] = "calm zone"
    elif "中高層" in zone or "中層" in zone:
        score += 1
    elif any(k in zone for k in ("商業", "準工業", "工業")):
        score -= 3; warn.append(f"zone {zone}")
    if r.get("building_m2") and r["building_m2"] >= 80:
        score += 2
    if p:
        score += max(0, (PRICE_CAP - p) / 500)
    if walk:
        score += max(0, (WALK_CAP - walk[2]) / 3)
        score += GOOD_STATIONS.get(walk[1], 0)
    score += CITIES[r["slug"]][1]
    if "荒川" in r.get("remarks", ""):
        score += 2; r["river"] = "荒川 mentioned"
    verdict = "reject" if rej else ("concern" if warn else "match")
    return verdict, rej + warn, round(score, 1)


def main():
    db = json.load(open(DB, encoding="utf-8")) if os.path.exists(DB) else {}
    if "--rescore" in sys.argv:  # re-apply the rules to saved records, no network
        for r in db.values():
            r["verdict"], r["reasons"], r["score"] = evaluate(r)
        json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("rescored", len(db))
        return
    for slug, (name, _) in CITIES.items():
        ids = collect_ids(slug)
        print(f"{name}: {len(ids)} listings found")
        for nc in ids:
            key = nc
            if key in db and db[key].get("fetched"):
                continue  # already fetched; price changes are caught by re-scan below
            rec = parse_detail(f"https://suumo.jp/chukoikkodate/saitama/{slug}/{nc}/", slug, nc)
            if rec is None:
                print(f"  {nc}: detail failed ({scan.LAST_ERROR})")
                continue
            db[key] = rec
            time.sleep(random.uniform(0.6, 1.2))
        json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in db.values():
        r["verdict"], r["reasons"], r["score"] = evaluate(r)
    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    counts = {}
    for r in db.values():
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("done", counts)


if __name__ == "__main__":
    main()
