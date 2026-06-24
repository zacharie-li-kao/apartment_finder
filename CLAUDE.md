You help me find an apartment to buy or to rent in the Tokyo area.

## Model & Performance

- **Use Haiku only:** Always use Claude Haiku 4.5 for all work — main agent, all subagents, all API calls. Pass `model: "haiku"` explicitly to every Agent() call to enforce this. This saves tokens and maintains consistent performance for this task.

## Websites to search

### Primary portals (buying & renting)
- https://suumo.jp — largest portal, must-check
- https://www.homes.co.jp — LIFULL HOME'S, comparable to SUUMO
- https://www.athome.co.jp — major aggregator
- https://realestate.yahoo.co.jp — Yahoo!不動産

### Agency-direct (may have exclusives before portal listing)
- https://www.rehouse.co.jp — 三井のリハウス (Mitsui Fudosan Realty)
- https://www.livable.co.jp — 東急リバブル (Tokyu Livable)
- https://www.stepon.co.jp — 住友不動産販売
- https://www.nomu.com — Nomura Real Estate
- https://www.century21.jp — Century 21 Japan

### New construction condominiums (新築マンション)
- https://www.major7.net — aggregates new condo pre-sales from major developers
- https://www.31sumai.com — 三井不動産レジデンシャル
- https://sumai-surfin.com — buyer-side analysis and ratings of new condos

### Renting (secondary — only if exceptional value)
- https://chintai.com — Chintai
- https://www.able.co.jp — ABLE
- https://www.minimini.jp — Minimini
- https://www.apaman.jp — Apaman

## Budget

- **Buying:** 40,000,000 yen (40M yen) — primary goal
- **Renting:** 130,000 yen/month — secondary; only consider if exceptional value for the price

## Area priorities

- **Most preferred:** Sumida-ku (especially near Skytree/押上, within 10-15 min walk) · Koto-ku
- **Acceptable if exceptional:** Chuo-ku, Minato-ku, Shibuya-ku (generally over budget — only add if a rare deal appears)
- **Lower priority:** Itabashi-ku, Nerima-ku, Kita-ku, Arakawa-ku (feel "far" to user — only add if strong value)
- **Deprioritised:** Edogawa-ku, Arakawa-ku — user finds these feel too far; only add if truly exceptional
- **Adachi-ku:** Not preferred, but consider if truly exceptional — must be extremely well connected (e.g. direct express to central Tokyo in ≤25 min), high floor, great view/light. Very high bar.
- **All must be within 45 minutes door-to-door to Tokyo Station**

## Preferences (near-essential — heavily weight in ranking)

- **View and light are near-essential:** South or SE facing strongly preferred; river view (Sumida River, Arakawa) or Skytree view are major bonuses
- Assess view potential from: floor number, compass orientation (方角), proximity to rivers/parks per address — flag likely views even if photos unavailable
- **High floor strongly preferred** (7F+ ideal; flag anything 5F+ as positive)
- Immediate occupancy (空家) preferred over tenant-occupied (オーナーチェンジ)
- Professional building management (全部委託) preferred over self-managed (自主管理)

## Hard red flags (automatic disqualifiers)

### Size & layout
- Smaller than 30m²
- Less than 1LDK

### Location & access
- More than 15 minutes walking from the nearest station
- Ground floor unit

### Building age & construction
- Built before 1982 (old seismic standard, pre-新耐震基準)
- No elevator for units above the 3rd floor
- Presence of asbestos (newborn at home — zero tolerance)

### Legal / ownership
- 借地権 (shakuchiken) — leasehold land, not owning the land
- 再建築不可 (saiken chiku fuka) — cannot be rebuilt if demolished
- 私道 (shidō) — private road access only, complicates permits and resale
- 容積率オーバー — illegal extension exceeding floor area ratio (banks won't finance)

### Condominium costs
- Monthly fees (管理費 + 修繕積立金 combined) above 30,000 yen/month

### Orientation
- North-facing only (北向き) — no southern exposure
