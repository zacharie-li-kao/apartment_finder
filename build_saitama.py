#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""saitama_db.json -> saitama.html (parallel report; does not touch index.html)."""
import html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "saitama_db.json")
OUT = os.path.join(HERE, "saitama.html")


def esc(s):
    return html.escape(str(s if s is not None else ""))


def card(r):
    walk = r.get("walk")
    walk_s = f"{walk[1]} 歩{walk[2]}分 ({walk[0]})" if walk else "—"
    p = r.get("price_man")
    price_s = f"{p:,.0f}万円" if p else "—"
    reasons = "; ".join(r.get("reasons", [])) or "no concerns"
    price_sort = p or 999999
    walk_sort = walk[2] if walk else 999
    return f"""
<article class="card {esc(r['verdict'])}" data-id="{esc(r['id'])}" data-verdict="{esc(r["verdict"])}" data-city="{esc(r["city"])}" data-score="{r.get('score', 0)}" data-price="{price_sort}" data-walk="{walk_sort}">
  <header><span class="badge {esc(r['verdict'])}">{esc(r['verdict'])}</span>
    <a href="{esc(r['url'])}" target="_blank" rel="noopener">{esc(r['city'])} · {esc(r.get('address',''))}</a></header>
  <div class="grid">
    <div><b>Price</b> {price_s}</div>
    <div><b>Land</b> {r.get('land_m2') or '—'} m² · <b>Building</b> {r.get('building_m2') or '—'} m²</div>
    <div><b>Layout</b> {esc(r.get('layout',''))} · <b>Built</b> {esc(r.get('built_year') or '—')}</div>
    <div><b>Walk</b> {esc(walk_s)}</div>
    <div><b>Best station in reach</b> {esc(r.get('best_station','—'))}</div>
    <div><b>Garden</b> {esc(r.get('garden','—'))}</div>
    <div><b>Also listed</b> {r.get('also_listed', 0)} other id(s)</div>
    <div><b>Zoning</b> {esc(r.get('zoning','—'))} {esc(r.get('calm',''))}</div>
    <div><b>Rights</b> {esc(r.get('rights','—'))} · <b>Coverage</b> {esc(r.get('coverage','—'))}</div>
    <div><b>Road</b> {esc(r.get('road','—'))}</div>
    <div><b>Score</b> {r.get('score', 0)}</div>
  </div>
  <p class="why">{esc(reasons)}</p>
  <details><summary>Remarks</summary><p>{esc(r.get('remarks',''))}</p></details>
  <div class="actions"><button data-act="star">☆ Star</button> <button data-act="discard">Discard</button></div>
</article>"""


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Saitama Houses</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a64;--card:#fff;--line:#e4e1d8;--ok:#2f7d4f;--warn:#b07a12;--bad:#a33b3b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#171715;--fg:#eeece6;--mut:#9a978d;--card:#22221f;--line:#3a3934}}
:root[data-theme="dark"]{--bg:#171715;--fg:#eeece6;--mut:#9a978d;--card:#22221f;--line:#3a3934}
body{background:var(--bg);color:var(--fg);font-family:system-ui,sans-serif;margin:0;padding:16px;max-width:960px;margin:auto}
h1{font-size:1.4rem;margin:.2rem 0}
.intro{color:var(--mut);font-size:.9rem}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.bar button,.actions button{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 10px;cursor:pointer}
.bar button.on{border-color:var(--fg);font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0}
.card.discard{opacity:.45}
.card header{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-weight:600}
.card header a{color:var(--fg)}
.badge{font-size:.75rem;padding:2px 8px;border-radius:999px;color:#fff}
.badge.match{background:var(--ok)}.badge.concern{background:var(--warn)}.badge.reject{background:var(--bad)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;font-size:.92rem;margin-top:8px}
.why{color:var(--mut);font-size:.85rem;margin:6px 0}
.note{border-left:3px solid var(--warn);padding:6px 10px;color:var(--mut);font-size:.85rem;margin:12px 0}
@media (max-width:600px){.grid{grid-template-columns:1fr}}
</style></head>
<body>
<h1>Saitama detached houses — parallel search</h1>
<p class="intro">Separate from the Tokyo apartment report. Budget ≤ 30M yen. Scope: Saitama-Urawa, Saitama-Omiya, Saitama-Minami, Saitama-Minuma, Kawaguchi, Warabi, Toda, Ageo. Walk-only station ≤ 15 min. Built 1989 or later. Ownership (所有権) only.</p>
<div class="note">Estimates, not verified facts: calm/road judgements come from zoning (用途地域) and road width only. Ground-floor school use depends on 兼用住宅 rules (non-residential part ≤ 50m² and under half the floor area) and local confirmation. Private-road (私道) listings are shown as concerns, not rejected.</div>
<div class="bar" id="filters">
  <button class="on" data-f="active">Active</button>
  <button data-f="match">Match</button>
  <button data-f="concern">Concern</button>
  <button data-f="discard">Discarded</button>
  <button data-f="all">All</button>
</div>
<div class="bar">
  <select id="city"><option value="">All cities</option></select>
</div>
<div class="bar" id="sorts">
  <button data-s="score">Best score</button>
  <button data-s="price-asc">Price: low → high</button>
  <button data-s="price-desc">Price: high → low</button>
  <button data-s="walk">Walk: nearest first</button>
</div>
<main id="list">__CARDS__</main>
<script>
const KEY = "saitama_flags_v1"; // separate from the apartment report's storage
function load(){try{return JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){return {}}}
function save(f){try{localStorage.setItem(KEY, JSON.stringify(f))}catch(e){}}
let flags = load(), filter = "active", cityF = "";
// city dropdown: one entry per city present in the report
[...new Set([...document.querySelectorAll(".card")].map(c=>c.dataset.city))].sort().forEach(n=>{
  document.getElementById("city").insertAdjacentHTML("beforeend", `<option value="${n}">${n}</option>`);
});
document.getElementById("city").addEventListener("change", e=>{ cityF = e.target.value; render(); });
function render(){
  document.querySelectorAll(".card").forEach(c=>{
    const id=c.dataset.id, f=flags[id]||{};
    c.classList.toggle("discard", !!f.discard);
    c.querySelector('[data-act="star"]').textContent = f.star ? "★ Starred" : "☆ Star";
    c.querySelector('[data-act="discard"]').textContent = f.discard ? "Undo discard" : "Discard";
    let show = filter==="all" || (filter==="discard" ? !!f.discard : !f.discard && (filter==="active" ? c.dataset.verdict!=="reject" : c.dataset.verdict===filter));
    show = show && (!cityF || c.dataset.city===cityF);
    c.style.display = show ? "" : "none";
  });
  document.querySelectorAll("#filters button").forEach(b=>b.classList.toggle("on", b.dataset.f===filter));
}
document.getElementById("filters").addEventListener("click", e=>{ if(e.target.dataset.f){ filter=e.target.dataset.f; render(); } });
// sort by reordering the cards in place; cards with no price/walk time sort last
const SORTS = {
  "score": (a,b)=>b.dataset.score-a.dataset.score,
  "price-asc": (a,b)=>a.dataset.price-b.dataset.price,
  "price-desc": (a,b)=>(+b.dataset.price>=999999)-(+a.dataset.price>=999999) || b.dataset.price-a.dataset.price,
  "walk": (a,b)=>a.dataset.walk-b.dataset.walk
};
document.getElementById("sorts").addEventListener("click", e=>{
  const s=e.target.dataset.s; if(!s) return;
  const list=document.getElementById("list");
  [...list.children].sort(SORTS[s]).forEach(c=>list.appendChild(c));
  document.querySelectorAll("#sorts button").forEach(b=>b.classList.toggle("on", b.dataset.s===s));
});
document.getElementById("list").addEventListener("click", e=>{
  const b=e.target.closest("button[data-act]"); if(!b) return;
  const id=b.closest(".card").dataset.id; const f=flags[id]||{};
  if(b.dataset.act==="star") f.star=!f.star; else f.discard=!f.discard;
  flags[id]=f; save(flags); render();
});
render();
</script>
</body></html>
"""


def main():
    import scan_saitama  # scoring lives there; mid-scan records are not scored yet
    db = json.load(open(DB, encoding="utf-8"))
    for r in db.values():  # always re-score so stale verdicts can't survive a rule change
        r["verdict"], r["reasons"], r["score"] = scan_saitama.evaluate(r)
    # Same house re-listed under several ids (same address, price, areas, year):
    # show the best-scoring listing once, and note the other ids on it.
    groups = {}
    for r in db.values():
        if r.get("gone"):  # listing no longer on SUUMO (set by recheck)
            continue
        key = (r.get("address"), r.get("price_man"), r.get("land_m2"), r.get("building_m2"), r.get("built_year"))
        groups.setdefault(key, []).append(r)
    rows = []
    for members in groups.values():
        best = max(members, key=lambda r: r.get("score", 0))
        best["also_listed"] = len(members) - 1
        rows.append(best)
    rows.sort(key=lambda r: (r.get("verdict") == "reject", -r.get("score", 0)))
    html_out = PAGE.replace("__CARDS__", "\n".join(card(r) for r in rows))
    open(OUT, "w", encoding="utf-8").write(html_out)
    print(f"wrote {OUT} with {len(rows)} houses")


if __name__ == "__main__":
    main()
