# Tokyo Apartment Watch

Automated hourly search for a flat to buy in Tokyo, ranked against the criteria in
`CLAUDE.md`. Open **`index.html`** — that is the whole product.

If your stars and discards do not survive a reload when you open the file
directly, run **`open.bat`** instead: it serves the same page at
`http://127.0.0.1:8777` and browser storage is guaranteed to stick there.

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
| `open.bat` | Opens the report over `http://127.0.0.1:8777` (guaranteed storage). |
| `watch.log` | One line per cycle plus any new/changed/delisted listings. |
| `archive/` | Everything from the previous three search campaigns. |

## The hourly loop

A Windows scheduled task named `TokyoApartmentWatch` runs `watch.bat` every hour.
It runs under your interactive session, so it only fires while you are logged in,
and it is set to `IgnoreNew` — a cycle that overruns will never collide with the
next one.

```
schtasks /Query  /TN "TokyoApartmentWatch"     # check it
schtasks /Run    /TN "TokyoApartmentWatch"     # run now
schtasks /Delete /TN "TokyoApartmentWatch" /F  # stop it
```

A cycle takes about **19 minutes**, so it always finishes well before the next
one starts. It re-checks every ward, fetches detail pages only for listings it
has never seen, records price changes, and rewrites `index.html`.

Delisting is deliberately cautious. SUUMO throttles and reshuffles its listing
ids, so a ward whose pages failed to fetch is skipped entirely, and a listing is
only marked sold after it has been missing from **two consecutive** clean scans.
A single absence proves nothing.

SUUMO answers bursts with `HTTP 503`. The scraper backs off exponentially, logs
the reason for every page it could not fetch, carries on with the rest of the
ward, and re-fetches any detail page that failed on an earlier cycle — so a
throttled run costs coverage for one hour, never permanently.

If a scraper fails outright, the `watch.log` line for that cycle starts with
`!! FAILED:` — the report is never allowed to shrink silently.

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

**Covered:** SUUMO (the bulk of the market), Nomura Real Estate (nomu.com) and
Mitsui Rehouse. The last two are agency-direct and often list a unit before it
syndicates to the portals — the "hidden gem" layer. Each card shows its source,
and the source dropdown filters by it.

**Probed and not usable over plain HTTP** (all would need a scripted browser):

| Site | What happens |
|---|---|
| at-home | Result list rendered client-side by Angular; HTML has only the filter widgets |
| Yahoo! Real Estate | 403 |
| LIFULL HOME'S | Page loads but sits behind AWS WAF |
| Tokyu Livable | Search is JavaScript-driven; no listings in the HTML |
| Sumitomo (stepon) | 403 |
| Century 21 | 404 on the ward-list URL; no stable server-rendered scheme found |
| sumai-surfin | 403 |
| major7 (new builds) | Server-rendered, but new-build pre-sales only — not yet wired in |

Adding any of these means driving a real browser on a slower schedule. Worth
doing if SUUMO and the two agency sites go quiet.
