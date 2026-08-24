#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Secondary / agency-direct sources -> db.json

SUUMO carries the bulk of the market, but agency-direct sites often list a unit
days before it reaches the portals, and some never syndicate at all.  This module
adds Nomura (nomu.com), Mitsui Rehouse, at-home and LIFULL HOME'S.  Records are
merged into the same db.json and scored by scan.evaluate().
"""
import json, os, re, time, random, html
from datetime import datetime, timezone, timedelta

import requests
import scan

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "db.json")
JST = timezone(timedelta(hours=9))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})

WARDS = scan.WARDS
SLUG = {"13101": "chiyoda", "13102": "chuo", "13103": "minato", "13104": "shinjuku",
        "13105": "bunkyo", "13106": "taito", "13107": "sumida", "13108": "koto",
        "13113": "shibuya", "13116": "toshima", "13117": "kita", "13118": "arakawa",
        "13119": "itabashi", "13120": "nerima", "13121": "adachi",
        "13122": "katsushika", "13123": "edogawa"}


def get(url, tries=2):
    for i in range(tries):
        try:
            r = S.get(url, timeout=30)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return ""


T = scan.txt


def keep(price, area, walk, year):
    if price and price > scan.HARD_PRICE_MAN:
        return False
    if area and area < scan.MIN_AREA - 2:
        return False
    if walk and walk > scan.MAX_WALK:
        return False
    if year and year < scan.MIN_YEAR:
        return False
    return True


# --------------------------------------------------------------- nomu.com ----
def nomu(sc, max_pages=12):
    ward = WARDS[sc][0]
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        h = get(f"https://www.nomu.com/mansion/area_tokyo/{sc}/?pager_page={page}")
        if not h:
            break
        blocks = re.split(r'(?=<a href="/mansion/id/)', h)
        got = 0
        for b in blocks[1:]:
            m = re.match(r'<a href="(/mansion/id/([A-Z0-9]+)/)"', b)
            if not m:
                continue
            bid, url = "nomu_" + m.group(2), "https://www.nomu.com" + m.group(1)
            if bid in seen:
                continue
            b = b[:12000]
            nm = re.match(r'<a href="/mansion/id/[A-Z0-9]+/"[^>]*>(.*?)</a>', b, re.S)
            name = T(nm.group(1)) if nm else ""
            loc = re.search(r'class="item_location">(.*?)</p>', b, re.S)
            acc = re.search(r'class="item_access">(.*?)</p>', b, re.S)
            pri = re.search(r'class="item_price">(.*?)</p>', b, re.S)
            pt = re.search(r'class="item_point">(.*?)</p>', b, re.S)
            t4 = re.search(r'item_td item_4">(.*?)</td>', b, re.S)
            t5 = re.search(r'item_td item_5">(.*?)</td>', b, re.S)
            p4 = [T(x) for x in re.findall(r"<p>(.*?)</p>", t4.group(1), re.S)] if t4 else []
            p5 = [T(x) for x in re.findall(r"<p>(.*?)</p>", t5.group(1), re.S)] if t5 else []
            price = scan.parse_price(T(pri.group(1))) if pri else None
            area = scan.parse_area(p4[0]) if p4 else None
            layout = p4[1] if len(p4) > 1 else ""
            d = p4[2] if len(p4) > 2 else ""
            year = scan.parse_year(p5[0]) if p5 else None
            floor = scan.parse_floor(p5[1].split("/")[0]) if len(p5) > 1 else None
            access = T(acc.group(1)) if acc else ""
            walk = scan.parse_walk(access)
            got += 1
            seen.add(bid)
            if not keep(price, area, walk, year):
                continue
            out.append({
                "id": bid, "url": url, "source": "Nomura (nomu.com)",
                "ward": ward, "ward_code": sc, "name": name or "(unnamed)",
                "blurb": T(pt.group(1)) if pt else "",
                "price_raw": f"{price}万円" if price else "",
                "address": "東京都" + (T(loc.group(1)) if loc else ""),
                "station_raw": access.replace("\n", " / "),
                "area_raw": p4[0] if p4 else "", "layout": layout,
                "built_raw": p5[0] if p5 else "",
                "direction": scan.DIRS.get(d.strip(), ""),
                "floor": floor,
                "structure": p5[1] if len(p5) > 1 else "",
                "units": p5[2] if len(p5) > 2 else "",
                "transport": access, "detail_ok": True,
            })
        if got == 0:
            break
        time.sleep(random.uniform(0.7, 1.3))
    return out


# ----------------------------------------------------------- rehouse (三井) ----
def rehouse(sc, max_pages=8):
    """Rehouse renders cards client-side, but ships a JSON-LD ItemList with
    name/price/url.  Filter on price there, then fetch details only for the
    handful that survive."""
    ward = WARDS[sc][0]
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        h = get(f"https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/{sc}/"
                f"?page={page}")
        if not h:
            break
        m = re.search(r'data-hid="productList">(\{.*?\})</script>', h, re.S)
        if not m:
            break
        try:
            items = json.loads(m.group(1))["itemListElement"]
        except Exception:
            break
        got = 0
        for it in items:
            o = it.get("item", {})
            url = o.get("offers", {}).get("url", "")
            bm = re.search(r"bkdetail/([A-Z0-9]+)/", url)
            if not bm:
                continue
            bid = "rehouse_" + bm.group(1)
            if bid in seen:
                continue
            seen.add(bid)
            got += 1
            try:
                price = int(float(o["offers"]["price"])) // 10000
            except Exception:
                price = None
            if price and price > scan.HARD_PRICE_MAN:
                continue
            out.append({
                "id": bid, "url": url, "source": "Mitsui Rehouse",
                "ward": ward, "ward_code": sc, "name": o.get("name", ""),
                "price_raw": f"{price}万円" if price else "",
                "needs_detail": True,
            })
        if got < 20:
            break
        time.sleep(random.uniform(0.7, 1.3))
    return [r for r in (rehouse_detail(r) for r in out) if r]


REH_KEYS = {"専有面積": "area_raw", "間取り": "layout", "階数 / 階建": "floor_raw",
            "築年月": "built_raw", "向き": "dir_raw", "バルコニー": "balcony_raw",
            "管理費等": "mgmt_raw", "修繕積立金": "repair_raw", "交通": "transport",
            "所在地": "address", "総戸数": "units", "土地権利": "tenure",
            "建物構造": "structure", "引渡時期": "handover",
            "現況": "handover_status", "管理形態": "mgmt_form", "備考": "notes_raw"}


def rehouse_detail(r):
    h = get(r["url"])
    if not h:
        return None
    f = {}
    for k, v in re.findall(
            r'class="table-header label"[^>]*>(.*?)</td>\s*'
            r'<td class="table-data content"[^>]*>(.*?)</td>', h, re.S):
        k = T(k)
        if k and k not in f:
            f[k] = T(v)
    for jp, key in REH_KEYS.items():
        if jp in f:
            r[key] = f[jp]
    r["station_raw"] = r.get("transport", "")
    r["handover"] = (r.get("handover_status", "") + " " + r.get("handover", "")).strip()
    best = ""
    for raw in re.findall(r'"description":\s*"((?:[^"\\]|\\.)*)"', h):
        try:
            d = json.loads('"' + raw + '"')
        except Exception:
            continue
        if len(d) > len(best):
            best = d
    if best:
        r["notes_raw"] = (r.get("notes_raw", "") + " " + best).strip()
    r["floor"] = scan.parse_floor(r.get("floor_raw", ""))
    d = (r.get("dir_raw") or "").strip()
    r["direction"] = scan.DIRS.get(d, "")
    r["mgmt_fee"] = scan.parse_yen(r.get("mgmt_raw", ""))
    r["repair_fee"] = scan.parse_yen(r.get("repair_raw", ""))
    r["fees"] = r["mgmt_fee"] + r["repair_fee"]
    r["mgmt_style"] = ("delegated" if "委託" in r.get("mgmt_form", "") else
                       "self-managed" if "自主" in r.get("mgmt_form", "") else "")
    r["blurb"] = re.sub(r"\s+", " ", r.get("notes_raw", "")).strip()[:200]
    if not keep(scan.parse_price(r.get("price_raw", "")),
                scan.parse_area(r.get("area_raw", "")),
                scan.parse_walk(r.get("transport", "")),
                scan.parse_year(r.get("built_raw", ""))):
        return None
    r["detail_ok"] = True
    time.sleep(0.3)
    return r


# -------------------------------------------------------------- at-home -------
def athome(sc, max_pages=8):
    ward = WARDS[sc][0]
    slug = SLUG.get(sc)
    if not slug:
        return []
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        h = get(f"https://www.athome.co.jp/mansion/chuko/tokyo/{slug}-city/list/"
                f"?page={page}")
        if not h:
            break
        got = 0
        for m in re.finditer(r'href="(/mansion/(\d{10,})/?)"', h):
            bid = "athome_" + m.group(2)
            if bid in seen:
                continue
            seen.add(bid)
            got += 1
            b = T(h[max(0, m.start() - 500):m.start() + 4000])
            price = scan.parse_price(b)
            area = scan.parse_area(b)
            walk = scan.parse_walk(b)
            year = scan.parse_year(b)
            lay = re.search(r"\b(\d[SLDKR]{1,4})\b", b)
            if not keep(price, area, walk, year):
                continue
            out.append({
                "id": bid, "url": "https://www.athome.co.jp" + m.group(1),
                "source": "at-home", "ward": ward, "ward_code": sc,
                "name": "", "blurb": "",
                "price_raw": f"{price}万円" if price else "",
                "area_raw": f"{area}m2" if area else "",
                "layout": lay.group(1) if lay else "",
                "built_raw": f"{year}年" if year else "",
                "station_raw": "", "address": "",
                "needs_detail": True,
            })
        if got == 0:
            break
        time.sleep(random.uniform(0.8, 1.4))
    return out


SOURCES = [("nomu", nomu), ("rehouse", rehouse), ("athome", athome)]


def main():
    db = json.load(open(DB, encoding="utf-8")) if os.path.exists(DB) else {}
    now = datetime.now(JST).isoformat(timespec="seconds")
    total = 0
    for label, fn in SOURCES:
        rows = []
        for sc in WARDS:
            try:
                r = fn(sc)
            except Exception as e:
                print(f"  {label}/{WARDS[sc][0]}: {e}", flush=True)
                r = []
            rows += r
        print(f"{label:<9} {len(rows):>4} in scope", flush=True)
        for r in rows:
            old = db.get(r["id"], {})
            merged = {**old, **{k: v for k, v in r.items() if v not in ("", None)}}
            merged.setdefault("first_seen", now)
            merged["last_seen"] = now
            merged["gone"] = False
            db[r["id"]] = scan.evaluate(merged)
        total += len(rows)

    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"gems: +{total} records merged; db now {len(db)}")


if __name__ == "__main__":
    main()
