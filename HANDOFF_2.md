# School Selector — Handoff 2
**Date**: 2026-03-01
**Status**: Website fully updated and pushed to gh-pages. Compare Schools and Nearby Schools tabs live.

---

## What Was Done (Previous Session)

### 1. Repo & Directory Cleanup

- **Identified nested git repos**: `/root/my-vault/.git` and `/root/my-vault/london_school_stats/.git` (formerly `school selector/`)
- **Revoked leaked GitHub PAT** that was embedded in `/root/my-vault/.git` remote URL
- **Removed** `/root/my-vault/.git` (stray Obsidian vault repo, no longer needed)
- **Renamed** directory `school selector/` → `london_school_stats/` to match GitHub repo name
- **Updated remote URLs** in both repos from `Feb26` → `london_school_stats`
- **Updated all path references** in: `.gitignore`, `.obsidian/workspace.json`, `.claude/settings.local.json`, `MEMORY.md`, `HANDOFF.md`
- Auth on the droplet works via `gh` CLI OAuth token — no action needed for new PAT

### 2. Compare Schools Tab Added to `report.html`

**Commit**: `3d2cf60`

Added a full **Compare Schools** tab alongside the existing Explorer and Borough tabs.

**Features:**
- Phase selector (KS2 / KS4 / KS5) filters both the search and the comparison table
- Searchable school picker — type to get a live dropdown, click to add
- Selected schools shown as removable chips; **Clear All** button resets selections
- Transposed comparison table: metrics are rows, schools are columns — easy side-by-side reading
- Phase-appropriate metrics shown per phase (e.g. P8/Att8/EBacc for KS4; RWM/Progress for KS2; VA/AAB for KS5)
- Pure client-side JS — no server required, works off the same self-contained `report.html`

---

## What Was Done (Session 3 — 2026-03-01)

### 3. Nearby Schools Tab

**Commits**: `301b70a`, `46a3fc9`, `f50fab1`

Added a **Nearby Schools** tab: enter any UK postcode (full or outward code) and get the 10 closest schools across all three phases.

#### How it works

**Build time** (`generate_report.py`):
- `POSTCODE` column added to `KS2_COLS`, `KS4_COLS`, `KS5_COLS` exports
- `STREET` and `LOCALITY` joined from the `schools` table via `URN` and embedded in the JSON data
- All school postcodes geocoded to precise lat/lng via **postcodes.io bulk API** (POST, 100 at a time) — 2,526 of 2,538 unique postcodes resolved. Coordinates stored in each school's JSON record as `lat`/`lng`

**Runtime** (browser JS):
- `DATA_NEARBY` constant built at page load: one entry per school record that has `lat`/`lng`, tagged with phase key/label
- On search: typed postcode resolved to lat/lng via `postcodes.io` REST API (tries full postcode first, falls back to outward code)
- Schools sorted by Haversine distance; top 10 shown in a table with school name, address, borough, type, phase badge, distance (km), and composite score

#### Accuracy note
First attempt used `pgeocode` outward-code centroids (~1 km accuracy). This caused Highgate Primary (N6 4ED) to appear 2.13 km from N2 0NL when the real distance is 0.71 km. Replaced with full-postcode geocoding via postcodes.io bulk API, which gives ~10 m accuracy.

#### Compare Schools ported into template
The Compare Schools tab existed only in `report.html` (added manually). It was ported back into `HTML_TEMPLATE` in `generate_report.py` so it survives future rebuilds.

#### Key implementation details
| Detail | Value |
|---|---|
| Geocoding library | postcodes.io bulk POST (no API key needed) |
| Postcodes resolved | 2,526 / 2,538 (12 unresolvable — very minor schools) |
| Schools excluded from Nearby | ~2 (null postcode in metrics tables) |
| Duplicate schools across phases | Expected — a school with KS4+KS5 appears twice, as different performance records |
| `venv` broken | Old `venv/` had a broken Python path (`school selector/` rename). Created `venv2/` with `python3 -m venv` — use this for rebuilds |

---

## Live Site

https://qiaohong.github.io/london_school_stats/report.html

Tabs:
1. **Primary (KS2)** — search/filter/sort all KS2 schools
2. **Secondary (KS4)** — search/filter/sort all KS4 schools
3. **Sixth Form (KS5)** — search/filter/sort all KS5 schools
4. **Boroughs** — borough-level average cards
5. **Compare Schools** — side-by-side metric comparison
6. **Nearby Schools** — postcode proximity search + interactive map

---

### 4. Interactive Map in Nearby Schools Tab

**Commit**: `15bb526`

Added a **Leaflet.js + OpenStreetMap** map below the Nearby Schools results table.

**Features:**
- Red circle marker for the searched postcode
- Coloured circle markers for each of the 10 nearest schools: green = KS2, blue = KS4, orange = KS5
- Click any marker for a popup showing school name, phase and distance
- Map auto-fits bounds to include all 11 markers with padding
- Uses Leaflet 1.9.4 from CDN + OpenStreetMap tiles — no API key required
- Map is lazily initialised on first search; `invalidateSize()` called after display to handle hidden-container sizing

**Files changed:**
| File | Change |
|---|---|
| `generate_report.py` | Leaflet CDN tags in `<head>`, `.nearby-map` CSS, map div in panel, map rendering in `searchNearby()` |

---

## Commits

| Hash | Message |
|---|---|
| `15bb526` | Add interactive map to Nearby Schools tab (Leaflet + OpenStreetMap) |
| `f50fab1` | Add address and postcode to Nearby Schools results |
| `46a3fc9` | Fix proximity search accuracy: use precise full-postcode geocoding |
| `301b70a` | Add Nearby Schools tab with postcode proximity search |
| `3d2cf60` | Add Compare Schools tab with multi-school side-by-side comparison |

---

## Current State of Repo

Branch: `gh-pages` (deployment branch — pushing here triggers GitHub Pages)

```
london_school_stats/
├── report.html          ← live website, ~1.3 MB, self-contained
├── generate_report.py   ← Step 4: regenerate HTML from DB (owns the HTML template)
├── compute_metrics.py   ← Step 3: compute composite scores
├── load_data.py         ← Step 1: load DfE CSVs into SQLite
├── quality_report.py    ← diagnostic only
├── schools.db           ← SQLite DB (gitignored)
├── data/                ← raw DfE files (gitignored)
├── venv/                ← BROKEN — do not use (bad Python path after rename)
├── venv2/               ← use this — created fresh, has pandas + pgeocode
├── .gitignore
├── HANDOFF.md
└── HANDOFF_2.md         ← this file
```

---

## How to Rebuild the Site

```bash
cd london_school_stats
/root/my-vault/london_school_stats/venv2/bin/python generate_report.py
# (geocodes ~2,538 postcodes via postcodes.io — takes ~30 sec with rate limiting)
git add report.html generate_report.py
git commit -m "Rebuild report"
git push origin gh-pages
```

If data has changed (new DfE files added):
```bash
venv2/bin/python load_data.py       # ~1 min
venv2/bin/python compute_metrics.py # ~30 sec
venv2/bin/python generate_report.py # ~30 sec (includes geocoding)
```

---

## Known Limitations (Unchanged)

- No 2024-25 absence data (DfE hasn't released `abs.csv` for that year)
- KS2 progress only available 2023-24 and 2024-25 (DfE suspended KS1-referenced progress in 2022-23)
- P8 for 2024-25 not yet published — some schools show 2023-24 P8
- Destinations data has ~16-month lag — 2024-25 destinations not yet available
