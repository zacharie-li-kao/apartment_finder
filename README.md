# Tokyo Apartment Watch

Automated hourly search for a flat to buy in Tokyo, ranked against the criteria in
`CLAUDE.md`. Open **`index.html`** — that is the whole product.

## Files

| File | What it is |
|---|---|
| `index.html` | The report. Double-click it. Sort, filter, star, discard. |
| `db.json` | Every listing ever seen, with its parsed fields, flags and score. |
| `flags.json` | *(optional)* Baseline stars/discards — see "Keeping flags forever". |
| `scan.py` | SUUMO scraper (17 wards, full pagination, detail pages). |
| `scan_gems.py` | Secondary/agency-direct sources: Nomura, Mitsui Rehouse. |
| `build.py` | Turns `db.json` into `index.html`. |
| `run.py` | One full cycle: scan → gems → build → append to `watch.log`. |
| `watch.bat` | What the hourly scheduled task runs. |
| `watch.log` | One line per cycle plus any new/changed/delisted listings. |
| `archive/` | Everything from the previous three search campaigns. |

## The hourly loop

A Windows scheduled task named `TokyoApartmentWatch` runs `watch.bat` every hour.

```
schtasks /Query  /TN "TokyoApartmentWatch"     # check it
schtasks /Run    /TN "TokyoApartmentWatch"     # run now
schtasks /Delete /TN "TokyoApartmentWatch" /F  # stop it
```

Each cycle re-checks every ward, fetches detail pages only for listings it has
never seen, marks vanished listings as delisted, records price changes, and
rewrites `index.html`.

## Starring and discarding

Click **☆ Star** or **Discard** on any card. It saves immediately in the browser
and survives every rebuild of `index.html` — listing IDs are stable, so the
hourly job never resets your choices.

Discarded listings are hidden but not lost: the **Discarded** filter shows them,
and clicking **Undo discard** brings one back.

### Keeping flags forever

Browser storage is per-browser. If you ever clear site data, or want the flags on
another machine, click **Copy flags**, paste the JSON into a file called
`flags.json` in this folder, and every future build starts from it.

## How listings are judged

- **Reject** (red ✕) — a hard red flag from `CLAUDE.md`: under 30 m², pre-1982,
  over 15 min walk, ground floor, leasehold, north-only, fees over ¥30,000/mo,
  or a layout below 1LDK. These are hidden from the default view.
- **Near-miss** (amber !) — over budget, self-managed, tenant-occupied, fees not
  published, or another soft concern. Shown, because an unusual feature can be
  worth the compromise.
- **Match** (green ✓) — no red flags, no concerns.

The **score** weights ward priority, price against the ¥40M budget, size, walk
time, floor, orientation and monthly fees, with bonuses for view/light signals
(Skytree, riverside, corner unit, top floor) and penalties for each concern.

Walk times count only minutes on foot from a station — bus-then-walk routes are
ignored, which is how SUUMO makes far-out flats look close.

## Coverage and known gaps

Covered: SUUMO (the bulk of the market), Nomura Real Estate (nomu.com), and
Mitsui Rehouse — the last two often list a unit before it syndicates to portals.

Not covered yet: at-home and Yahoo! Real Estate render their result lists in
JavaScript and block plain HTTP scraping, so they need browser automation.
LIFULL HOME'S sits behind AWS WAF. Adding these means driving a real browser on
a slower schedule — worth doing if the current sources go quiet.
