#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tokyo apartment scanner -> db.json

Scrapes SUUMO (chuko mansion, for-sale) across the target wards, paginating every
page, enriches new listings from their detail page, scores them, and merges into
db.json.  Run repeatedly; only unseen listing ids cost a detail fetch.
"""
import json, os, re, sys, time, random, html
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "db.json")
JST = timezone(timedelta(hours=9))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})

# ward code -> (english, priority tier)  tier 1 = most preferred
WARDS = {
    "13107": ("Sumida", 1),
    "13108": ("Koto", 1),
    "13106": ("Taito", 2),
    "13102": ("Chuo", 2),
    "13103": ("Minato", 2),
    "13113": ("Shibuya", 2),
    "13105": ("Bunkyo", 2),
    "13101": ("Chiyoda", 2),
    "13104": ("Shinjuku", 3),
    "13116": ("Toshima", 3),
    "13122": ("Katsushika", 3),
    "13117": ("Kita", 3),
    "13118": ("Arakawa", 3),
    "13119": ("Itabashi", 3),
    "13120": ("Nerima", 3),
    "13123": ("Edogawa", 4),
    "13121": ("Adachi", 4),
}

# generous pre-filter: budget 4000man, allow near-misses up to 4600man
MAX_PRICE_MAN = 5000   # SUUMO enum; real cut-off applied in code
HARD_PRICE_MAN = 4600
MIN_AREA = 30.0
MAX_WALK = 17          # filtered in code (SUUMO et= is an enum)
MIN_YEAR = 1982

LIST_URL = ("https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/?ar=030&bs=011&ta=13"
            "&sc={sc}&cn=9999999&cmb=0&kb=1&kt={kt}&mb={mb}&mt=9999999&et={et}"
            "&pc=50&page={page}")


def get(url, tries=3):
    for i in range(tries):
        try:
            r = S.get(url, timeout=30)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return ""


def txt(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- parsing ----
def parse_list(page_html, ward):
    out = []
    blocks = re.split(r'<div class="property_unit(?=[ "])', page_html)[1:]
    for b in blocks:
        m = re.search(r'href="(/ms/chuko/tokyo/sc_[^/]+/nc_(\d+)/)"', b)
        if not m:
            continue
        url, nc = "https://suumo.jp" + m.group(1), m.group(2)
        f = {}
        for k, v in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", b, re.S):
            f.setdefault(txt(k), txt(v))
        t = re.search(r'property_unit-title">\s*<a[^>]*>(.*?)</a>', b, re.S)
        out.append({
            "id": nc, "url": url, "ward": ward,
            "name": f.get("物件名", ""),
            "blurb": txt(t.group(1)) if t else "",
            "price_raw": f.get("販売価格", ""),
            "address": f.get("所在地", ""),
            "station_raw": f.get("沿線・駅", ""),
            "area_raw": f.get("専有面積", ""),
            "layout": f.get("間取り", ""),
            "balcony_raw": f.get("バルコニー", ""),
            "built_raw": f.get("築年月", ""),
        })
    return out


def parse_price(s):
    """'2380万円' / '1億2800万円' -> man-yen int"""
    s = re.sub(r"[,\s]", "", s)
    oku = re.search(r"(\d+(?:\.\d+)?)億", s)
    man = re.search(r"(?:億)?(\d+(?:\.\d+)?)万", s)
    v = 0.0
    if oku:
        v += float(oku.group(1)) * 10000
    if man:
        v += float(man.group(1))
    return int(v) if v else None


def parse_area(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*m", s)
    return float(m.group(1)) if m else None


def parse_walk(s):
    """Minutes on foot from the nearest station.  Segments that route via a bus
    (…バス5分…歩3分) are ignored — that 3 min is from the bus stop, not the station."""
    if not s:
        return None
    segs = [x for x in re.split(r"\[[^\]]*\]|/", s) if x.strip()]
    ws = []
    for seg in segs:
        if "バス" in seg or "車" in seg:
            continue
        ws += [int(x) for x in re.findall(r"(?:徒歩|歩)\s*(\d+)\s*分", seg)]
    return min(ws) if ws else None


def parse_year(s):
    m = re.search(r"(\d{4})年", s)
    return int(m.group(1)) if m else None


def parse_floor(s):
    m = re.search(r"(\d+)\s*階", s)
    if m:
        return int(m.group(1))
    if "地下" in s or "B1" in s:
        return 0
    return None


def parse_yen(s):
    m = re.search(r"([\d,]+)\s*円", s)
    return int(m.group(1).replace(",", "")) if m else 0


DIRS = {"南": "S", "南東": "SE", "南西": "SW", "東": "E", "西": "W",
        "北": "N", "北東": "NE", "北西": "NW"}


def fetch_detail(rec):
    h = get(rec["url"])
    if not h:
        rec["detail_ok"] = False
        return rec
    f = {}
    for k, v in re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", h, re.S):
        k = re.sub(r"ヒント|（必須）|※.*", "", txt(k)).strip()
        if k and k not in f:
            f[k] = txt(v)

    def g(*names):
        for n in names:
            if n in f:
                return f[n]
        return ""

    rec["floor"] = parse_floor(g("所在階", "所在階/構造・階建"))
    rec["structure"] = g("構造・階建て", "所在階/構造・階建")
    d = g("向き").strip()
    rec["direction"] = DIRS.get(d, d if d and d != "-" else "")
    rec["mgmt_fee"] = parse_yen(g("管理費"))
    rec["repair_fee"] = parse_yen(g("修繕積立金"))
    rec["fees"] = rec["mgmt_fee"] + rec["repair_fee"]
    rec["mgmt_style"] = "delegated" if "委託" in g("管理費") else (
        "self-managed" if "自主" in g("管理費") else "")
    rec["tenure"] = g("敷地の権利形態")
    rec["units"] = g("総戸数")
    rec["handover"] = g("引渡可能時期")
    rec["zoning"] = g("用途地域")
    rec["reform"] = g("リフォーム")
    rec["listed_on"] = g("情報提供日")
    rec["notes_raw"] = g("その他概要・特記事項")
    rec["transport"] = g("交通")
    rec["detail_ok"] = True
    return rec


# ---------------------------------------------------------------- scoring ----
def evaluate(r):
    """Attach derived fields, kill/warn flags, and a 0-100 score."""
    r["price"] = parse_price(r.get("price_raw", ""))
    r["area"] = parse_area(r.get("area_raw", ""))
    r["walk"] = parse_walk(r.get("station_raw", "") + " " + r.get("transport", ""))
    r["year"] = parse_year(r.get("built_raw", ""))
    r["station"] = r.get("station_raw", "")

    kill, warn, plus = [], [], []
    P, A, W, Y = r["price"], r["area"], r["walk"], r["year"]
    F = r.get("floor")
    fees = r.get("fees", 0)
    tenure = r.get("tenure", "")
    layout = r.get("layout", "")
    blob = " ".join(str(r.get(k, "")) for k in
                    ("notes_raw", "blurb", "name", "structure", "zoning"))

    # --- hard red flags -------------------------------------------------
    if A and A < 30:
        kill.append(f"Under 30 m² ({A} m²)")
    if Y and Y < 1982:
        kill.append(f"Pre-1982 seismic code ({Y})")
    if W and W > 15:
        kill.append(f"{W} min walk (>15)")
    if F == 1:
        kill.append("Ground floor")
    if "借地" in tenure or "借地" in blob:
        kill.append("Leasehold land (借地権)")
    if "再建築不可" in blob:
        kill.append("Cannot be rebuilt (再建築不可)")
    if "私道" in blob:
        warn.append("Private-road access (私道) mentioned")
    if "容積率オーバー" in blob or "超過" in blob:
        warn.append("Possible floor-area-ratio overage")
    if fees > 30000:
        kill.append(f"Fees ¥{fees:,}/mo (>30,000)")
    if re.match(r"^[123456]?[KRD]$|^1K$|^1R$|^ワンルーム", layout) or layout in (
            "1K", "1R", "1DK", "2K", "ワンルーム"):
        kill.append(f"Layout {layout} (below 1LDK)")
    if r.get("direction") == "N":
        kill.append("North-facing only")
    if P and P > 4000:
        warn.append(f"Over budget by ¥{(P-4000)*10000:,}")

    # --- positives ------------------------------------------------------
    if r.get("direction") in ("S", "SE", "SW"):
        plus.append(f"{r['direction']}-facing")
    if F and F >= 7:
        plus.append(f"High floor ({F}F)")
    elif F and F >= 5:
        plus.append(f"Mid-high floor ({F}F)")
    if "空家" in r.get("handover", "") or "即" in r.get("handover", ""):
        plus.append("Immediate occupancy")
    if r.get("mgmt_style") == "delegated":
        plus.append("Professionally managed")
    if r.get("mgmt_style") == "self-managed":
        warn.append("Self-managed building (自主管理)")
    if "オーナーチェンジ" in blob:
        warn.append("Tenant-occupied (owner change)")
    for kw, label in (("スカイツリー", "Skytree view mentioned"),
                      ("隅田川", "Sumida river nearby"),
                      ("荒川", "Arakawa river nearby"),
                      ("河川敷", "Riverside"),
                      ("眺望", "View highlighted"),
                      ("リバー", "River view mentioned"),
                      ("角部屋", "Corner unit"),
                      ("最上階", "Top floor"),
                      ("リノベ", "Renovated"), ("リフォーム済", "Renovated"),
                      ("公園", "Near park"), ("ルーフバルコニー", "Roof balcony")):
        if kw in blob and label not in plus:
            plus.append(label)
    if W and W <= 5:
        plus.append(f"{W} min to station")
    if r.get("reform") and r["reform"] not in ("-", ""):
        plus.append("Reform info listed")

    # --- score ----------------------------------------------------------
    s = 50.0
    tier = WARDS.get(r.get("ward_code", ""), (None, 3))[1]
    s += {1: 18, 2: 8, 3: 0, 4: -8}.get(tier, 0)
    if P:
        s += max(-20, min(14, (4000 - P) / 100.0))          # cheaper = better
    if A:
        s += max(-8, min(14, (A - 40) * 0.7))               # bigger = better
    if W:
        s += max(-10, min(10, (10 - W) * 2.0))
    if Y:
        s += max(-8, min(10, (Y - 1990) * 0.35))
    if F:
        s += max(-6, min(12, (F - 3) * 1.6))
    if r.get("direction") in ("S",):
        s += 10
    elif r.get("direction") in ("SE", "SW"):
        s += 7
    elif r.get("direction") in ("E", "W"):
        s += 1
    elif r.get("direction") in ("NE", "NW"):
        s -= 4
    if fees:
        s += max(-8, min(5, (18000 - fees) / 2000.0))
    else:
        warn.append("Monthly fees not published")
    s += 1.8 * len([p for p in plus if "view" in p.lower() or "Skytree" in p
                    or "river" in p.lower()])
    s -= 4 * len(warn)
    s -= 25 * len(kill)

    r["kill"] = kill
    r["warn"] = warn
    r["plus"] = plus
    r["score"] = round(max(0, min(100, s)), 1)
    r["verdict"] = "reject" if kill else ("watch" if warn else "match")
    return r


# ------------------------------------------------------------------ main ----
def scan_ward(sc, max_pages=25):
    name = WARDS[sc][0]
    found, seen_ids = [], set()
    for page in range(1, max_pages + 1):
        url = LIST_URL.format(sc=sc, kt=MAX_PRICE_MAN, mb=int(MIN_AREA),
                              et=9999999, page=page)
        h = get(url)
        if not h:
            break
        rows = parse_list(h, name)
        if not rows:
            break
        new = []
        for r in rows:
            if r["id"] in seen_ids:
                continue
            seen_ids.add(r["id"])
            new.append(r)
        if not new:
            break
        for r in new:
            r["ward_code"] = sc
        for r in new:
            pr = parse_price(r["price_raw"]); ar = parse_area(r["area_raw"])
            wk = parse_walk(r["station_raw"]); yr = parse_year(r["built_raw"])
            if pr and pr > HARD_PRICE_MAN: continue
            if ar and ar < MIN_AREA - 2: continue
            if wk and wk > MAX_WALK: continue
            if yr and yr < MIN_YEAR: continue
            found.append(r)
        if len(rows) < 50:
            break
        time.sleep(random.uniform(0.6, 1.2))
    print(f"  {name:<11} {len(found):>4} listings", flush=True)
    return found


def main():
    only = sys.argv[1:] or list(WARDS)
    db = {}
    if os.path.exists(DB):
        db = json.load(open(DB, encoding="utf-8"))
    now = datetime.now(JST).isoformat(timespec="seconds")

    print("Scanning SUUMO...", flush=True)
    listings = []
    for sc in only:
        if sc in WARDS:
            listings += scan_ward(sc)

    live = {r["id"] for r in listings}
    fresh = [r for r in listings if r["id"] not in db]
    print(f"\n{len(listings)} in scope, {len(fresh)} new -> fetching details",
          flush=True)

    if fresh:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for i, r in enumerate(ex.map(fetch_detail, fresh), 1):
                if i % 25 == 0:
                    print(f"  detail {i}/{len(fresh)}", flush=True)

    for r in listings:
        old = db.get(r["id"], {})
        if r["id"] in db:
            merged = {**old, **{k: v for k, v in r.items() if v not in ("", None)}}
        else:
            merged = r
            merged["first_seen"] = now
        merged["last_seen"] = now
        merged["gone"] = False
        if old.get("price") and r.get("price_raw"):
            np_ = parse_price(r["price_raw"])
            if np_ and np_ != old["price"]:
                merged.setdefault("price_history", []).append(
                    {"date": now[:10], "from": old["price"], "to": np_})
        db[r["id"]] = evaluate(merged)

    # mark disappeared listings from wards we just scanned
    for k, v in db.items():
        if v.get("ward_code") in only and k not in live:
            v["gone"] = True

    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    act = [v for v in db.values() if not v.get("gone")]
    print(f"\ndb.json: {len(db)} total, {len(act)} active, "
          f"{sum(1 for v in act if v['verdict'] != 'reject')} qualifying")


if __name__ == "__main__":
    main()
