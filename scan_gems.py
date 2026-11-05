#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Secondary / agency-direct sources -> db.json

SUUMO carries the bulk of the market, but agency-direct sites often list a unit
days before it reaches the portals, and some never syndicate at all.  This module
adds Nomura (nomu.com), Mitsui Rehouse, Yahoo!不動産, Tokyu Livable, at-home and LIFULL HOME'S.  Records are
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


# ------------------------------------------------------------ Yahoo!不動産 -----
def yahoo(sc, max_pages=12):
    """List cards carry floor / facing / area / layout / name / price, so the
    detail page is fetched only for units that pass those cheap filters."""
    ward = WARDS[sc][0]
    out, seen = [], set()
    known = json.load(open(DB, encoding="utf-8")) if os.path.exists(DB) else {}
    for page in range(1, max_pages + 1):
        h = get(f"https://realestate.yahoo.co.jp/used/mansion/search/03/13/{sc}/"
                + (f"?page={page}" if page > 1 else ""))
        if not h:
            break
        got = 0
        for card in re.split(r'(?=<div class="ListCassette2 )', h)[1:]:
            # one card per unit; agency offers inside it share the same unit
            m = re.search(r'detail_corp/b(\d+)/"\s+target="_blank"\s+'
                          r'data-cl-params="_cl_link:room', card)
            if not m or ("yahoo_" + m.group(1)) in seen:
                continue
            bid = "yahoo_" + m.group(1)
            seen.add(bid)
            got += 1
            tt = re.search(r'ListCassette2__ttl__txt--inner">(.*?)</h2>', card, re.S)
            p = [x.strip() for x in T(tt.group(1)).split("/")] if tt else []
            fl, d, ar, lay = (p + [""] * 4)[:4]
            nm = re.search(r'buildingName&quot;:&quot;(.*?)&quot;', card)
            pr = re.search(r'ListCassette2__info__price">(.*?)</li>', card, re.S)
            price = scan.parse_price(T(pr.group(1))) if pr else None
            if price and price >= 9999:  # 9,999万円 is the undisclosed-price placeholder
                price = None
            area = scan.parse_area(ar)
            if price is None or not keep(price, area, None, None):
                continue  # undisclosed price: skipped, usually far over budget
            url = f"https://realestate.yahoo.co.jp/used/mansion/detail_corp/b{m.group(1)}/"
            if known.get(bid, {}).get("address"):  # detail already stored: refresh list fields only
                out.append({"id": bid, "url": url, "source": "Yahoo!不動産", "ward": ward,
                            "ward_code": sc, "price_raw": f"{price}万円", "area_raw": ar.replace(" ", ""),
                            "layout": lay, "direction": scan.DIRS.get(d, ""), "floor": scan.parse_floor(fl)})
                continue
            time.sleep(random.uniform(0.7, 1.3))
            dh = get(url)
            if not dh or "築年月" not in dh:  # a stub/throttled page has no spec table
                continue
            f = {T(k): T(v) for k, v in re.findall(
                r'<dt class="DetailTable__2rows__head">(.*?)</dt>\s*'
                r'<dd class="DetailTable__2rows__detail">(.*?)</dd>', dh, re.S)}
            ex = {T(k): scan.parse_yen(T(v)) for k, v in re.findall(
                r'exPrice__ttl">(.*?)</span>\s*<em[^>]*>(.*?)</em>', dh, re.S)}
            loc = re.search(r'class="locTxt">\s*<span[^>]*>(.*?)</span>', dh, re.S)
            acc = re.search(r'class="accTtl">交通</div>\s*<div class="accTxt">(.*?)</div>', dh, re.S)
            access = T(acc.group(1)) if acc else ""
            walk = scan.parse_walk(access)
            year = scan.parse_year(f.get("築年月", ""))
            if not keep(price, area, walk, year):
                continue
            mgmt_form = f.get("管理形態", "")
            out.append({
                "id": bid, "url": url, "source": "Yahoo!不動産",
                "ward": ward, "ward_code": sc, "name": T(nm.group(1)) if nm else "",
                "blurb": "", "price_raw": f"{price}万円" if price else "",
                "address": T(loc.group(1)) if loc else "",
                "station_raw": access, "transport": access,
                "area_raw": ar.replace(" ", ""), "layout": lay,
                "built_raw": f.get("築年月", ""),
                "direction": scan.DIRS.get(d, ""), "floor": scan.parse_floor(fl),
                "structure": f.get("構造・工法", ""), "units": f.get("総戸数", ""),
                "tenure": f.get("土地権利形態", ""),
                "mgmt_fee": ex.get("管理費", 0), "repair_fee": ex.get("修繕積立金", 0),
                "fees": ex.get("管理費", 0) + ex.get("修繕積立金", 0),
                "mgmt_style": ("delegated" if "委託" in mgmt_form else
                               "self-managed" if "自主" in mgmt_form else ""),
                "detail_ok": True,
            })
        if got == 0:
            break
        time.sleep(random.uniform(0.7, 1.3))
    return out


# ------------------------------------------------------- Tokyu Livable -----
def livable(sc, max_pages=12):
    ward = WARDS[sc][0]
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        h = get(f"https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/a{sc}/?page={page}")
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
        items = json.loads(m.group(1))["props"]["pageProps"].get("propertyList", []) if m else []
        got = 0
        for o in items:
            pid = o["propertyCd"]
            if pid in seen:
                continue
            seen.add(pid)
            got += 1
            det = [T(x) for x in o.get("propertyDetail", [])]
            layout = det[0] if det else ""
            area_s = next((x for x in det if re.match(r"[\d.]+\s*(m|㎡)", x)), "")
            built = next((x for x in det if "築" in x), "")
            fl = next((x for x in det if "階" in x and "／" in x), "")
            dr = next((x for x in det if x.endswith("向き")), "").replace("向き", "")
            price = o["priceModel"]["price"] // 10000
            access = " / ".join(o.get("access", []))
            area = scan.parse_area(area_s.replace("m2", "m²")) if area_s else None
            year = scan.parse_year(built)
            walk = scan.parse_walk(access)
            if not keep(price, area, walk, year):
                continue
            out.append({
                "id": "livable_" + pid, "url": "https://www.livable.co.jp/mansion/" + pid + "/",
                "source": "Tokyu Livable", "ward": ward, "ward_code": sc,
                "name": o.get("propertyName", ""), "price_raw": f"{price}万円",
                "address": o.get("address", ""), "station_raw": access, "transport": access,
                "area_raw": area_s.replace("m2", "m²"), "layout": layout, "built_raw": built,
                "direction": scan.DIRS.get(dr, ""), "floor": scan.parse_floor(fl.split("／")[0]),
                "structure": fl, "detail_ok": False,
            })
        if got < 25:
            break
        time.sleep(random.uniform(0.7, 1.3))
    return out


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


# at-home renders its result list client-side (Angular); plain HTTP returns only
# the filter widgets.  Left in place but disabled until driven by a real browser.
SOURCES = [("nomu", nomu), ("rehouse", rehouse), ("yahoo", yahoo), ("livable", livable)]


def main():
    db = json.load(open(DB, encoding="utf-8")) if os.path.exists(DB) else {}
    now = datetime.now(JST).isoformat(timespec="seconds")
    total = 0
    for label, fn in SOURCES:
        rows, ok = [], True
        for sc in WARDS:
            try:
                r = fn(sc)
            except Exception as e:
                print(f"  {label}/{WARDS[sc][0]}: {e}", flush=True)
                r, ok = [], False
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
        # only sweep for delistings when every ward of this source came back clean,
        # otherwise a transient failure would wipe the source from the report
        src_name = rows[0]["source"] if rows else None
        if ok and rows:
            live = {r["id"] for r in rows}
            for k, v in db.items():
                if v.get("source") != src_name:
                    continue
                if k in live:
                    v["misses"] = 0
                    v["gone"] = False
                else:
                    v["misses"] = v.get("misses", 0) + 1
                    v["gone"] = v["misses"] >= 2

    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"gems: +{total} records merged; db now {len(db)}")


if __name__ == "__main__":
    main()
