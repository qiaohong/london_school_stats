# School Selector — Handoff Notes
**Date**: 2026-03-01
**Status**: Steps 1–4 complete. `report.html` built and ready to push to gh-pages.

---

## What Was Done

### Files Created / Modified
| File | Status |
|---|---|
| `load_data.py` | Complete — loads 68 tables (47 raw, 13 meta, 8 model) |
| `compute_metrics.py` | Complete — computes 5 metrics tables, writes to DB |
| `generate_report.py` | Complete — produces self-contained `report.html` |
| `quality_report.py` | Written (diagnostic, not needed to re-run unless data changes) |
| `report.html` | Complete — ~1MB, self-contained, no external deps |
| `schools.db` | Exists — 68 tables populated |
| `.gitignore` | Added — excludes venv/, data/, schools.db |

### To deploy the report

```bash
cd "school selector"
git add report.html generate_report.py compute_metrics.py load_data.py quality_report.py .gitignore HANDOFF.md
git commit -m "Add school performance report and data pipeline"
git push origin gh-pages
```

Then visit: https://qiaohong.github.io/school-report/report.html

---

## Pipeline Overview

```
data/ (raw DfE CSVs + XLSXs)
  → load_data.py      → schools.db (raw_*, meta_*, model tables)
  → compute_metrics.py → schools.db (metrics_ks2/ks4/ks5/la/type)
  → generate_report.py → report.html
```

### To rebuild from scratch

```bash
source venv/bin/activate
python load_data.py       # ~1 min (fast because large XLSXs are skipped)
python compute_metrics.py # ~30 sec
python generate_report.py # ~5 sec
```

---

## schools.db — Model Tables

| Table | Rows | Years | Notes |
|---|---|---|---|
| `schools` | 9,308 | 2022–2025 | All London school records |
| `ks4_results` | 2,593 | 2022–2025 | Secondary GCSE data |
| `ks2_results` | 5,527 | 2022–2025 | Primary; 219 legacy cols dropped |
| `ks5_results` | 1,575 | 2022–2025 | Sixth form; 48 FE college rows removed |
| `census` | 8,935 | 2022–2025 | Pupil characteristics |
| `absences` | 4,902 | 2022–2024 | No 2024-25 abs.csv available |
| `ks4_pupil_destinations` | 1,784 | 2022–2025 | Post-16 outcomes |
| `ks5_student_destinations` | 1,230 | 2022–2025 | Post-18 outcomes |

### Metrics Tables

| Table | Rows | Description |
|---|---|---|
| `metrics_ks4` | 907 | 1 row/school: P8, Att8, basics5, EBacc, absence, destinations, trend, composite |
| `metrics_ks2` | 1,889 | 1 row/school: RWM%, progress, absence, FSM gap, trend, composite |
| `metrics_ks5` | 562 | 1 row/school: VA, AAB%, HE destinations, absence, trend, composite |
| `metrics_la` | 99 | Borough averages for each phase |
| `metrics_type` | 13 | School type averages |

---

## Composite Score Design (0–100)

Each component is percentile-ranked within London. Missing → 50 (neutral/median).

| Phase | Components |
|---|---|
| **KS2** | RWM expected (30%), avg progress (40%), absence (15%), RWM higher (15%) |
| **KS4** | Progress 8 (35%), grade 5+ E&M (25%), EBacc entry (10%), absence (15%), destinations education (15%) |
| **KS5** | A-level value added (40%), AAB facilitating (25%), HE destinations (25%), absence (10%) |

---

## Cleaning Decisions

- Suppression markers (`SUPP`, `NE`, `NP`, `LOW`) → NaN in all model tables
- KS2: 219 legacy KS1 prior-attainment columns (≥50% null across 3 years) dropped
- KS5: 48 FE college rows removed (school-based sixth forms only)
- KS4 provisional excluded; KS4 final/revised used
- MAT-level and subject-level data excluded (school-level summaries only)
- All school types included (independents, special schools, through-schools)
- KS4: P8MEA pulled from most recent year with non-null P8 (2024-25 provisional omits it)
- Percentage columns with `%` suffix (2024-25 data) handled by `to_num()` stripping `%`

---

## Known Limitations

- No 2024-25 absence data (no `abs.csv` in that year's DfE release)
- KS2 progress (reading/writing/maths) only available for 2023-24 and 2024-25 due to DfE suspension of KS1-referenced progress in 2022-23
- P8 for 2024-25 not yet published; some schools show 2023-24 P8 in the report
- Destinations data: ~16-month lag, so 2024-25 destinations not yet available

---

## Key File Structure

```
school selector/
├── data/
│   ├── 2022-2023/        # DfE CSVs + XLSXs
│   ├── 2023-2024/
│   ├── 2024-2025/        # "revised" suffix; no abs.csv
│   └── metadata/         # LA codes, column metadata, etc.
├── venv/                 # Python env: pandas 3.0.1, openpyxl 3.1.5
├── load_data.py          # Step 1: DB population
├── compute_metrics.py    # Step 3: Metrics computation
├── generate_report.py    # Step 4: HTML report generation
├── quality_report.py     # Diagnostic only
├── report.html           # ← The webpage (~1MB, self-contained)
├── schools.db            # ← SQLite DB (~excluded from git)
├── .gitignore
└── HANDOFF.md
```
