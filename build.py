#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db.json -> index.html  (self-contained, English, with persistent star/discard)"""
import json, os, re
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
JST = timezone(timedelta(hours=9))

WARD_JP = {"Sumida": "墨田区", "Koto": "江東区", "Taito": "台東区", "Chuo": "中央区",
           "Minato": "港区", "Shibuya": "渋谷区", "Bunkyo": "文京区",
           "Chiyoda": "千代田区", "Shinjuku": "新宿区", "Toshima": "豊島区",
           "Katsushika": "葛飾区", "Kita": "北区", "Arakawa": "荒川区",
           "Itabashi": "板橋区", "Nerima": "練馬区", "Edogawa": "江戸川区",
           "Adachi": "足立区"}

LINE_JP = [("東武伊勢崎線", "Tobu Isesaki"), ("東武スカイツリーライン", "Tobu Skytree"),
           ("都営浅草線", "Toei Asakusa"), ("都営大江戸線", "Toei Oedo"),
           ("都営新宿線", "Toei Shinjuku"), ("都営三田線", "Toei Mita"),
           ("東京メトロ半蔵門線", "Metro Hanzomon"), ("東京メトロ東西線", "Metro Tozai"),
           ("東京メトロ日比谷線", "Metro Hibiya"), ("東京メトロ有楽町線", "Metro Yurakucho"),
           ("東京メトロ千代田線", "Metro Chiyoda"), ("東京メトロ丸ノ内線", "Metro Marunouchi"),
           ("東京メトロ銀座線", "Metro Ginza"), ("東京メトロ副都心線", "Metro Fukutoshin"),
           ("東京メトロ南北線", "Metro Namboku"), ("ＪＲ総武線", "JR Sobu"),
           ("JR総武線", "JR Sobu"), ("ＪＲ京葉線", "JR Keiyo"),
           ("ＪＲ山手線", "JR Yamanote"), ("ＪＲ常磐線", "JR Joban"),
           ("ＪＲ中央線", "JR Chuo"), ("ＪＲ埼京線", "JR Saikyo"),
           ("ＪＲ京浜東北線", "JR Keihin-Tohoku"), ("つくばエクスプレス", "Tsukuba Express"),
           ("京成押上線", "Keisei Oshiage"), ("京成本線", "Keisei Main"),
           ("東急", "Tokyu"), ("西武", "Seibu"), ("りんかい線", "Rinkai"),
           ("ゆりかもめ", "Yurikamome"), ("日暮里・舎人ライナー", "Nippori-Toneri")]


def en_station(s, prefer_nearest=True):
    """Turn '東武伊勢崎線「東向島」徒歩8分' into 'Tobu Isesaki - 東向島, 8 min walk'."""
    if not s:
        return ""
    if prefer_nearest:
        s = re.sub(r"\[.*?\]", " ", s)
        parts = [p for p in re.split(r"(?<=分)\s+", s) if "分" in p]
        if parts:
            def w(p):
                m = re.search(r"(\d+)分", p)
                return int(m.group(1)) if m else 99
            s = min(parts, key=w)
    line = ""
    for jp, en in LINE_JP:
        if jp in s:
            line = en
            break
    st = re.search(r"「(.+?)」", s)
    bits = [b for b in (line, st.group(1) if st else "") if b]
    out = " · ".join(bits) if bits else re.sub(r"\s+", " ", s)[:40]
    return out


def money(man):
    if not man:
        return "—"
    return f"¥{man*10000:,}" if man < 10000 else f"¥{man*10000:,}"


def man_str(man):
    if not man:
        return "—"
    return f"{man/100:.2f}M".rstrip("0").rstrip(".") + " ¥" if False else \
        f"¥{man*10_000:,.0f}"


DIR_LABEL = {"S": "South", "SE": "South-East", "SW": "South-West", "E": "East",
             "W": "West", "N": "North", "NE": "North-East", "NW": "North-West"}


def load():
    db = json.load(open(os.path.join(HERE, "db.json"), encoding="utf-8"))
    rows = []
    for r in db.values():
        if r.get("gone"):
            continue
        rows.append({
            "id": r["id"], "url": r["url"],
            "name": r.get("name") or "(unnamed)",
            "blurb": r.get("blurb", ""),
            "ward": r.get("ward", ""), "wardJp": WARD_JP.get(r.get("ward", ""), ""),
            "address": r.get("address", ""),
            "price": r.get("price"), "area": r.get("area"),
            "layout": r.get("layout", ""), "year": r.get("year"),
            "floor": r.get("floor"), "walk": r.get("walk"),
            "dir": r.get("direction") or "",
            "dirLabel": DIR_LABEL.get(r.get("direction") or "", ""),
            "fees": r.get("fees", 0), "tenure": r.get("tenure", ""),
            "units": r.get("units", ""), "handover": r.get("handover", ""),
            "structure": r.get("structure", ""),
            "station": (en_station(r.get("transport") or r.get("station_raw", ""))
                        + (f" — {r['walk']} min walk" if r.get("walk") else "")),
            "stationJp": r.get("station_raw", ""),
            "score": r.get("score", 0), "verdict": r.get("verdict", "watch"),
            "kill": r.get("kill", []), "warn": r.get("warn", []),
            "plus": r.get("plus", []),
            "first": (r.get("first_seen") or "")[:10],
            "last": (r.get("last_seen") or "")[:10],
            "hist": r.get("price_history", []),
            "ppm": round(r["price"] * 10000 / r["area"]) if r.get("price") and r.get("area") else None,
        })
    # collapse the same physical unit listed by several agents
    groups = {}
    for r in rows:
        k = (r["price"], r["area"], r["floor"], r["year"], r["ward"])             if r["price"] and r["area"] else ("id", r["id"])
        groups.setdefault(k, []).append(r)
    merged = []
    for g in groups.values():
        g.sort(key=lambda x: (-len(x["plus"]), len(x["name"])))
        best = dict(g[0])
        best["name"] = re.sub(r"^[■★☆◆●【】\s]+|[■★☆◆●【】\s]+$", "", best["name"]) or best["name"]
        best["agents"] = len(g)
        best["alt"] = [x["url"] for x in g[1:]]
        best["first"] = min(x["first"] for x in g if x["first"]) if any(x["first"] for x in g) else best["first"]
        merged.append(best)
    merged.sort(key=lambda x: -x["score"])
    return merged


TPL = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tokyo Apartment Watch</title>
<style>
:root{
  --bg:#f6f5f2; --card:#fff; --ink:#171512; --mut:#736c60; --line:#e2ded6;
  --accent:#8a3d1f; --good:#1f6b45; --warnc:#9a6a12; --badc:#8f2f2f;
  --chip:#efece5;
}
:root:not([data-theme=light]) { }
@media (prefers-color-scheme: dark){:root:not([data-theme=light]){
  --bg:#14130f; --card:#1d1c18; --ink:#eceae4; --mut:#a09889; --line:#302e28;
  --accent:#e0895f; --good:#63c295; --warnc:#dcae52; --badc:#e0796f; --chip:#26241f;
}}
:root[data-theme=dark]{
  --bg:#14130f; --card:#1d1c18; --ink:#eceae4; --mut:#a09889; --line:#302e28;
  --accent:#e0895f; --good:#63c295; --warnc:#dcae52; --badc:#e0796f; --chip:#26241f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px 80px}
header{padding:44px 0 20px;border-bottom:1px solid var(--line);margin-bottom:22px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.02em;font-weight:650}
.sub{color:var(--mut);font-size:14px}
.stats{display:flex;flex-wrap:wrap;gap:22px;margin-top:18px}
.stat b{display:block;font-size:22px;font-weight:650;letter-spacing:-.01em}
.stat span{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--mut)}

.bar{position:sticky;top:0;z-index:20;background:var(--bg);padding:12px 0;
  border-bottom:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.bar button,.bar select,.bar input{font:inherit;font-size:13px;padding:6px 12px;
  border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;cursor:pointer}
.bar input{cursor:text;min-width:170px}
.bar button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.spacer{flex:1}

.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;margin-bottom:12px;display:grid;
  grid-template-columns:58px 1fr auto;gap:16px;align-items:start}
.card.star{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
.rank{text-align:center}
.rank b{display:block;font-size:21px;font-weight:650;letter-spacing:-.02em}
.rank span{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}
.title{font-size:17px;font-weight:600;letter-spacing:-.01em;margin:0 0 3px}
.title a{color:inherit;text-decoration:none;border-bottom:1px solid var(--line)}
.title a:hover{border-color:var(--accent);color:var(--accent)}
.where{font-size:13px;color:var(--mut);margin-bottom:9px}
.facts{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.f{background:var(--chip);border-radius:6px;padding:3px 9px;font-size:12.5px;white-space:nowrap}
.f b{font-weight:600}
.price{font-size:19px;font-weight:650;letter-spacing:-.02em;white-space:nowrap}
.ppm{font-size:11.5px;color:var(--mut);white-space:nowrap;text-align:right}
.flags{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.fl{font-size:11.5px;padding:2px 8px;border-radius:999px;border:1px solid}
.fl.p{color:var(--good);border-color:color-mix(in srgb,var(--good) 40%,transparent)}
.fl.w{color:var(--warnc);border-color:color-mix(in srgb,var(--warnc) 40%,transparent)}
.fl.k{color:var(--badc);border-color:color-mix(in srgb,var(--badc) 45%,transparent)}
.blurb{font-size:12.5px;color:var(--mut);margin-top:7px;font-style:italic}
.acts{display:flex;flex-direction:column;gap:6px;align-items:flex-end}
.acts button{font:inherit;font-size:12px;padding:5px 11px;border-radius:999px;
  border:1px solid var(--line);background:transparent;color:var(--mut);cursor:pointer}
.acts button:hover{border-color:var(--ink);color:var(--ink)}
.acts button.active{background:var(--accent);border-color:var(--accent);color:#fff}
.new{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:600}
h2.sec{font-size:12px;text-transform:uppercase;letter-spacing:.11em;color:var(--mut);
  margin:34px 0 12px;font-weight:600}
.empty{color:var(--mut);padding:40px 0;text-align:center;font-size:14px}
footer{margin-top:50px;padding-top:18px;border-top:1px solid var(--line);
  color:var(--mut);font-size:12px}
@media(max-width:720px){.card{grid-template-columns:1fr;gap:10px}
  .acts{flex-direction:row}.rank{text-align:left}}
</style>
</head>
<body>

<div class="wrap">
<header>
  <h1>Tokyo Apartment Watch</h1>
  <div class="sub">Buy · budget ¥40,000,000 · Sumida &amp; Koto first · updated __TS__ JST</div>
  <div class="stats">
    <div class="stat"><b id="s-tot">0</b><span>Live listings</span></div>
    <div class="stat"><b id="s-match">0</b><span>Clean matches</span></div>
    <div class="stat"><b id="s-watch">0</b><span>Near-misses</span></div>
    <div class="stat"><b id="s-star">0</b><span>Starred</span></div>
    <div class="stat"><b id="s-disc">0</b><span>Discarded</span></div>
  </div>
</header>

<div class="bar">
  <button data-v="all" class="on">All</button>
  <button data-v="match">Matches</button>
  <button data-v="watch">Near-miss</button>
  <button data-v="star">★ Starred</button>
  <button data-v="disc">Discarded</button>
  <select id="ward"><option value="">All wards</option></select>
  <select id="sort">
    <option value="score">Sort: score</option>
    <option value="price">Sort: price ↑</option>
    <option value="ppm">Sort: ¥ per m² ↑</option>
    <option value="area">Sort: size ↓</option>
    <option value="floor">Sort: floor ↓</option>
    <option value="new">Sort: newest</option>
  </select>
  <input id="q" placeholder="Search name, station, address…">
  <span class="spacer"></span>
  <button id="copy" title="Copy your stars/discards as JSON — paste into flags.json to keep them forever">Copy flags</button>
  <button id="reset" title="Clear all stars and discards">Reset flags</button>
</div>

<div id="list"></div>

<footer>
  Stars and discards are saved in this browser and survive page rebuilds — listing IDs are stable.
  Data scraped from SUUMO (中古マンション). Fees = 管理費 + 修繕積立金.
  Scores weight ward, price, size, walk time, floor, orientation and fees.
</footer>
</div>

<script>
const DATA = __DATA__;
const SEED = __SEED__;              // baseline from flags.json, if present
const KEY = 'apt-flags-v1';
let flags = {...SEED};
try { flags = {...SEED, ...JSON.parse(localStorage.getItem(KEY) || '{}')}; } catch(e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(flags)); } catch(e){} };
const st = id => flags[id] || 0;   // 0 none, 1 star, 2 discard

let view = 'all', ward = '', sort = 'score', q = '';

const wsel = document.getElementById('ward');
[...new Set(DATA.map(d => d.ward))].sort().forEach(w => {
  const o = document.createElement('option'); o.value = o.textContent = w; wsel.append(o);
});

const yen = n => n == null ? '—' : '¥' + (n * 10000).toLocaleString();
const esc = s => (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function card(d, i) {
  const s = st(d.id);
  const facts = [];
  if (d.area)   facts.push(`<span class="f"><b>${d.area}</b> m²</span>`);
  if (d.layout) facts.push(`<span class="f">${esc(d.layout)}</span>`);
  if (d.floor)  facts.push(`<span class="f"><b>${d.floor}F</b>${d.structure?' / '+esc(d.structure):''}</span>`);
  if (d.dirLabel) facts.push(`<span class="f">${d.dirLabel} facing</span>`);
  if (d.year)   facts.push(`<span class="f">Built ${d.year}</span>`);
  if (d.fees)   facts.push(`<span class="f">Fees <b>¥${d.fees.toLocaleString()}</b>/mo</span>`);
  if (d.units)  facts.push(`<span class="f">${esc(d.units)} units</span>`);
  if (d.handover) facts.push(`<span class="f">Handover: ${esc(d.handover)}</span>`);
  if (d.agents > 1) facts.push(`<span class="f">${d.agents} agents listing this</span>`);

  const fl = [...d.plus.map(x=>`<span class="fl p">✓ ${esc(x)}</span>`),
              ...d.warn.map(x=>`<span class="fl w">! ${esc(x)}</span>`),
              ...d.kill.map(x=>`<span class="fl k">✕ ${esc(x)}</span>`)].join('');

  return `<div class="card${s===1?' star':''}" data-id="${d.id}">
    <div class="rank"><b>${d.score}</b><span>score</span></div>
    <div>
      <div class="title"><a href="${d.url}" target="_blank" rel="noopener">${esc(d.name)}</a></div>
      <div class="where">${esc(d.ward)} ${d.wardJp} · ${esc(d.station)} · ${esc(d.address)}</div>
      <div class="facts">${facts.join('')}</div>
      <div class="flags">${fl}</div>
      ${d.blurb ? `<div class="blurb">“${esc(d.blurb)}”</div>` : ''}
    </div>
    <div>
      <div class="price">${yen(d.price)}</div>
      <div class="ppm">${d.ppm ? '¥'+d.ppm.toLocaleString()+' / m²' : ''}</div>
      <div class="acts" style="margin-top:10px">
        <button class="star${s===1?' active':''}">${s===1?'★ Starred':'☆ Star'}</button>
        <button class="disc${s===2?' active':''}">${s===2?'Undo discard':'Discard'}</button>
      </div>
    </div>
  </div>`;
}

function render() {
  let rows = DATA.filter(d => {
    const s = st(d.id);
    if (view === 'disc')  return s === 2;
    if (s === 2) return false;
    if (view === 'star')  return s === 1;
    if (view === 'match') return d.verdict === 'match';
    if (view === 'watch') return d.verdict === 'watch';
    return d.verdict !== 'reject' || s === 1;
  });
  if (ward) rows = rows.filter(d => d.ward === ward);
  if (q) {
    const t = q.toLowerCase();
    rows = rows.filter(d => (d.name+d.station+d.stationJp+d.address+d.ward+d.blurb)
      .toLowerCase().includes(t));
  }
  const cmp = {
    score: (a,b)=>b.score-a.score,
    price: (a,b)=>(a.price??9e9)-(b.price??9e9),
    ppm:   (a,b)=>(a.ppm??9e9)-(b.ppm??9e9),
    area:  (a,b)=>(b.area??0)-(a.area??0),
    floor: (a,b)=>(b.floor??0)-(a.floor??0),
    new:   (a,b)=>(b.first||'').localeCompare(a.first||'') || b.score-a.score,
  }[sort];
  rows.sort(cmp);

  document.getElementById('list').innerHTML = rows.length
    ? rows.map(card).join('')
    : '<div class="empty">Nothing matches these filters.</div>';

  const vals = Object.values(flags);
  document.getElementById('s-tot').textContent   = DATA.length;
  document.getElementById('s-match').textContent = DATA.filter(d=>d.verdict==='match'&&st(d.id)!==2).length;
  document.getElementById('s-watch').textContent = DATA.filter(d=>d.verdict==='watch'&&st(d.id)!==2).length;
  document.getElementById('s-star').textContent  = vals.filter(v=>v===1).length;
  document.getElementById('s-disc').textContent  = vals.filter(v=>v===2).length;
}

document.getElementById('list').addEventListener('click', e => {
  const btn = e.target.closest('button'); if (!btn) return;
  const id = e.target.closest('.card').dataset.id;
  const want = btn.classList.contains('star') ? 1 : 2;
  flags[id] = st(id) === want ? 0 : want;
  if (!flags[id]) delete flags[id];
  save(); render();
});
document.querySelectorAll('.bar button[data-v]').forEach(b => b.onclick = () => {
  document.querySelectorAll('.bar button[data-v]').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); view = b.dataset.v; render();
});
wsel.onchange = e => { ward = e.target.value; render(); };
document.getElementById('sort').onchange = e => { sort = e.target.value; render(); };
document.getElementById('q').oninput = e => { q = e.target.value; render(); };
const rb = document.getElementById('reset');
let armed = false;
rb.onclick = () => {
  if (!armed) { armed = true; rb.textContent = 'Click again to confirm';
    setTimeout(() => { armed = false; rb.textContent = 'Reset flags'; }, 4000); return; }
  flags = {}; save(); armed = false; rb.textContent = 'Reset flags'; render();
};
const cb = document.getElementById('copy');
cb.onclick = async () => {
  const txt = JSON.stringify(flags, null, 1);
  try { await navigator.clipboard.writeText(txt); cb.textContent = 'Copied ✓'; }
  catch(e) {
    const ta = document.createElement('textarea');
    ta.value = txt; document.body.append(ta); ta.select();
    document.execCommand('copy'); ta.remove(); cb.textContent = 'Copied ✓';
  }
  setTimeout(() => cb.textContent = 'Copy flags', 2000);
};
render();
</script>
</body>
</html>
"""


def main():
    rows = load()
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    seed = {}
    fp = os.path.join(HERE, "flags.json")
    if os.path.exists(fp):
        try:
            seed = json.load(open(fp, encoding="utf-8"))
        except Exception:
            seed = {}
    out = TPL.replace("__DATA__", json.dumps(rows, ensure_ascii=False)) \
             .replace("__SEED__", json.dumps(seed)) \
             .replace("__TS__", ts)
    p = os.path.join(HERE, "index.html")
    open(p, "w", encoding="utf-8").write(out)
    print(f"index.html written — {len(rows)} live listings, "
          f"{sum(1 for r in rows if r['verdict']=='match')} matches, "
          f"{sum(1 for r in rows if r['verdict']=='watch')} near-misses")


if __name__ == "__main__":
    main()
