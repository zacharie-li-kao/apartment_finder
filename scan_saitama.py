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
BASE = "https://suumo.jp/chukoikkodate/{pref}/{sc}/"
TOKYO_SLUGS = {"sc_setagaya", "sc_nerima", "sc_katsushika", "sc_edogawa", "sc_itabashi", "sc_kita"}


def pref(slug):
    return "tokyo" if slug in TOKYO_SLUGS else "saitama"

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
    # Along the Shonan-Shinjuku line around Omiya/Urawa (added on request)
    "sc_saitamashikita":   ("Saitama-Kita", 2),
    "sc_saitamashinishi":  ("Saitama-Nishi", 2),
    "sc_saitamashisakura": ("Saitama-Sakura", 1),
    "sc_saitamashimidori": ("Saitama-Midori", 1),
    "sc_saitamashiiwatsuki": ("Saitama-Iwatsuki", 1),
    "sc_okegawa":          ("Okegawa", 1),
    "sc_kitamoto":         ("Kitamoto", 1),
    "sc_konosu":           ("Konosu", 1),
    # Tokyo-edge cities with fast links (added on request)
    "sc_kawagoe":          ("Kawagoe", 2),
    "sc_wako":             ("Wako", 2),
    "sc_shiki":            ("Shiki", 2),
    "sc_niiza":            ("Niiza", 1),
    "sc_asaka":            ("Asaka", 1),
    # Tokyo wards near the border (added on request; SUUMO path is /tokyo/)
    "sc_setagaya":         ("Setagaya", 2),
    "sc_nerima":           ("Nerima", 1),
    "sc_katsushika":       ("Katsushika", 2),
    "sc_edogawa":          ("Edogawa", 1),
    "sc_itabashi":         ("Itabashi", 2),
    "sc_kita":             ("Kita", 2),
}

PRICE_CAP = 3000        # 万円 (30M yen)
WALK_CAP = 15           # minutes to nearest station
# Very close to central Tokyo: a 20-minute walk to the station is acceptable
NEAR_TOKYO = {"Kawaguchi", "Warabi", "Toda", "Wako", "Asaka",
              "Setagaya", "Nerima", "Katsushika", "Edogawa", "Itabashi", "Kita"}
NEAR_TOKYO_WALK_CAP = 20
MIN_YEAR = 1989

# Station quality is the biggest score term: a house near a major hub beats a
# cheaper house far from one. Tier points are added once, for the best station
# reachable within the walk cap (not only the nearest).
STATION_TIER = {}
for names, pts in [
    (["大宮", "浦和", "川口", "川越"], 25),           # major hubs
    (["西川口", "蕨", "戸田", "南浦和", "与野", "北浦和", "上尾", "和光市"], 12),  # solid
    (["東浦和", "志木", "新座", "朝霞", "北戸田", "中浦和", "武蔵浦和"], 6),       # local
]:
    for n in names:
        STATION_TIER[n] = pts


def collect_ids(slug):
    """Walk every page of one city list until a page adds no new listing."""
    seen, out = set(), []
    for page in range(1, 60):
        url = BASE.format(pref=pref(slug), sc=slug) + (f"?page={page}" if page > 1 else "")
        page_html = scan.get(url)
        if not page_html:
            print(f"  {slug} p{page}: fetch failed ({scan.LAST_ERROR}); stopping city")
            break
        found = re.findall(r"/chukoikkodate/%s/%s/(nc_\d+)/" % (pref(slug), re.escape(slug)), page_html)
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


def walk_entries(transport):
    """Every walk-only station (ignores bus-then-walk routes)."""
    out = []
    for entry in transport.split("[ 乗り換え案内 ]"):
        if "バス" in entry:
            continue
        m = re.search(r"([^\s「]*)「([^」]+)」\s*歩(\d+)分", entry)
        if m:
            out.append((m.group(1), m.group(2), int(m.group(3))))
    return out


def walk_info(transport):
    """Nearest walk-only station."""
    entries = walk_entries(transport)
    return min(entries, key=lambda e: e[2]) if entries else None


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
        # Under 25M the saving matters more; from 25M to 40M it only gently counts.
        score += 3 + (2500 - p) / 1000 if p < 2500 else 3 * (PRICE_CAP - p) / 1500
    if walk:
        score += max(0, (WALK_CAP - walk[2]) / 3)
    # best station reachable within the city's walk cap, not only the nearest
    reach = [e for e in walk_entries(r.get("transport", "")) if e[2] <= cap]
    best_station = max(reach, key=lambda e: STATION_TIER.get(e[1], 0), default=None)
    if best_station:
        score += STATION_TIER.get(best_station[1], 0)
        r["best_station"] = f"{best_station[1]} 歩{best_station[2]}分"
    # Shonan-Shinjuku line: the user's preferred direct line, extra bonus
    if any("湘南新宿" in e[0] for e in reach):
        score += 10; r["best_station"] = r.get("best_station", "") + " · 湘南新宿ライン"
    # garden: any yard/garden wording in the remarks or features
    if re.search(r"庭|ガーデン|garden|テラス", r.get("remarks", "") + " " + r.get("blurb", "")):
        score += 8; r["garden"] = "garden mentioned"
    score += CITIES[r["slug"]][1]
    if "荒川" in r.get("remarks", ""):
        score += 2; r["river"] = "荒川 mentioned"
    verdict = "reject" if rej else ("concern" if warn else "match")
    return verdict, rej + warn, round(score, 1)


def recheck(db):
    """Re-fetch every saved house: record price changes and listings that went
    away. A failed fetch (503 etc.) is 'unknown', never 'delisted'."""
    changes = []
    for n, (key, r) in enumerate(db.items(), 1):
        if n % 100 == 0:  # progress and periodic save: a throttled run must not lose its work
            print(f"  recheck {n}/{len(db)}, changes so far {len(changes)}", flush=True)
            json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not r.get("fetched"):
            continue
        raw = scan.get(r["url"], tries=2)
        if not raw:
            continue  # unknown: could be throttling
        t = unicodedata.normalize("NFKC", scan.txt(raw))
        if "売却済" in t or "掲載終了" in t or "販売終了" in t or "価格" not in t:
            if not r.get("gone"):
                r["gone"] = True
                changes.append({"id": key, "type": "delisted", "url": r["url"]})
            continue
        fresh = parse_detail(r["url"], r["slug"], key)
        if fresh and fresh.get("price_man") != r.get("price_man"):
            changes.append({"id": key, "type": "price", "url": r["url"],
                            "from": r.get("price_man"), "to": fresh.get("price_man")})
            r["price_man"] = fresh.get("price_man")
        time.sleep(random.uniform(0.6, 1.2))
    return changes


def main():
    db = json.load(open(DB, encoding="utf-8")) if os.path.exists(DB) else {}
    if "--recheck" in sys.argv:  # re-fetch saved houses: price changes and delistings
        changes = recheck(db)
        json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(changes, open(os.path.join(HERE, "saitama_changes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("recheck done:", len(changes), "changes")
        return
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
            rec = parse_detail(f"https://suumo.jp/chukoikkodate/{pref(slug)}/{slug}/{nc}/", slug, nc)
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
