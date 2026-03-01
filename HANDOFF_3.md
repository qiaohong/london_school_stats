# School Selector — Handoff 3
**Date**: 2026-03-01
**Status**: Website fully updated and pushed to gh-pages. 7 tabs live.

---

## Live Site

https://qiaohong.github.io/london_school_stats/report.html

| Tab | Description |
|---|---|
| Primary (KS2) | Search, filter and sort all 1,889 London primary schools |
| Secondary (KS4) | Search, filter and sort all 907 London secondary schools |
| Sixth Form (KS5) | Search, filter and sort all 562 London sixth forms |
| Boroughs | Borough-level average cards for all phases |
| Compare Schools | Side-by-side metric comparison for selected schools |
| Nearby Schools | Postcode + radius search with phase/type/admissions filters and interactive map |
| Appendix | Score methodology, data sources, known limitations |

---

## Current State of Repo

Branch: `gh-pages` (pushing here deploys to GitHub Pages)
Latest commit: `f69c004`

```
london_school_stats/
├── report.html            ← live website, ~1.7 MB, self-contained
├── generate_report.py     ← Step 4: regenerate HTML from DB (owns the full HTML template)
├── compute_metrics.py     ← Step 3: compute composite scores and write metrics tables
├── load_data.py           ← Step 1: load DfE CSVs into SQLite
├── quality_report.py      ← diagnostic only, not needed for normal rebuilds
├── schools.db             ← SQLite DB (gitignored)
├── data/                  ← raw DfE files (gitignored)
├── venv/                  ← BROKEN — do not use (bad Python path after rename)
├── venv2/                 ← use this for all Python commands
├── .gitignore
├── HANDOFF.md             ← session 1–2 notes
├── HANDOFF_2.md           ← session 3–4 notes
├── HANDOFF_3.md           ← this file
├── london_school_stats_1.md
├── london_school_stats_2.md
└── london_school_stats_3.md
```

---

## How to Rebuild the Site

```bash
cd /home/claude/my-vault/london_school_stats
venv2/bin/python generate_report.py
# geocodes ~2,538 postcodes via postcodes.io — takes ~30 sec
git add report.html generate_report.py
git commit -m "Rebuild report"
git push origin gh-pages
```

If data has changed (new DfE files added):
```bash
venv2/bin/python load_data.py        # ~1 min
venv2/bin/python compute_metrics.py  # ~30 sec
venv2/bin/python generate_report.py  # ~30 sec (includes geocoding)
```

---

## Data Summary

| Table | Rows | Notes |
|---|---|---|
| `schools` | 9,308 | 3 rows per URN (one per academic year 2022–25) |
| `metrics_ks2` | 1,889 | 1 row per primary school, latest year |
| `metrics_ks4` | 907 | 1 row per secondary school, latest year |
| `metrics_ks5` | 562 | 1 row per sixth form, latest year |
| `metrics_la` | 99 | Borough averages per phase |
| `metrics_type` | 13 | School type averages |

Ofsted coverage: 2,688 of ~2,800 schools in scope (~96%). Source: DfE school info 2022-23 file (2023-24 and 2024-25 files dropped Ofsted columns).

---

## Composite Score Design (0–100)

Each component is percentile-ranked within London (0 = lowest, 100 = highest). Missing values → 50 (neutral/median). Weights are judgement calls, not from any official methodology.

| Phase | Components & Weights |
|---|---|
| KS2 | avg progress 40%, RWM expected 30%, absence (inverted) 15%, RWM higher 15% |
| KS4 | Progress 8 35%, grade 5+ E&M 25%, absence (inverted) 15%, destinations education 15%, EBacc 10% |
| KS5 | A-level value added 40%, AAB facilitating 25%, HE destinations 25%, absence (inverted) 10% |

---

## Nearby Schools — Implementation Notes

- `DATA_NEARBY` is built client-side from `DATA_KS2` + `DATA_KS4` + `DATA_KS5` (one record per school per phase)
- School postcodes geocoded at build time via postcodes.io bulk POST API (2,526 / 2,538 resolved)
- Runtime search: postcode → lat/lng via postcodes.io (full postcode first, falls back to outward code)
- Filters: radius (≤5 km), phase (KS2/KS4/KS5), broad type (MINORGROUP), admissions (Selective/Non-selective)
- Cap: 50 results
- Map: Leaflet 1.9.4 + OpenStreetMap tiles, no API key needed
- Coincident markers (schools sharing the same postcode) are fanned out in a ~30 m circle so all are visible

---

## Known Limitations

- No 2024-25 absence data (DfE hasn't released `abs.csv` for that year)
- KS2 progress only available 2023-24 and 2024-25 (DfE suspended KS1-referenced progress in 2022-23)
- P8 for 2024-25 not yet published — some schools show 2023-24 P8
- Destinations data has ~16-month lag — 2024-25 destinations not yet available for most schools
- Ofsted ratings sourced from 2022-23 DfE file; may not reflect latest published inspections
