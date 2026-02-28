# Project Handoff — School Report Database
Last updated: 2026-02-28 (session 2)

---

## What This Project Does
Builds a SQLite database of primary and secondary schools in **London and Surrey**, combining data from:
- Ofsted (inspection grades)
- DfE (attainment, absence, exclusions, applications/offers)

---

## Project Location
All files in: `/root/my-vault/school selector/`

```
school selector/
├── fetch_ofsted_data.py          ✅ Done & working
├── fetch_dfe_performance.py      ✅ Done & working
├── fetch_supplementary_data.py   ✅ Done & working
├── ofsted_schools.db             ✅ ALL 8 TABLES FULLY LOADED
├── venv/                         Python virtual environment
└── data/
    ├── Management_information_..._31_Jan_2026.csv   ✅ Downloaded
    ├── ks2_institution_level_2024_25.csv            ✅ Downloaded
    ├── ks4_institution_level_2023_24.csv            ✅ Downloaded
    ├── AppsandOffers_2024_SchoolLevel.csv           ✅ Manually SCP'd from local machine
    ├── absence_school_level_2023_24.csv             ✅ Downloaded
    └── exclusions_school_level_2023_24.csv          ✅ Downloaded
```

---

## Current Database State

| Table | Status | Rows |
|-------|--------|------|
| `schools` | ✅ Loaded | 2,617 (London + Surrey, Primary + Secondary) |
| `inspections` | ✅ Loaded | 2,617 |
| `judgements` | ✅ Loaded | 2,617 — uses new **OEIF framework** grades |
| `primary_performance` | ✅ Loaded | 1,850 |
| `secondary_performance` | ✅ Loaded | 542 |
| `absence` | ✅ Loaded | 2,526 |
| `exclusions` | ✅ Loaded | 326 |
| `applications` | ✅ Loaded | 2,533 |

---

## What To Do Next

**The database is complete.** All data is loaded. The obvious next step is building a query/reporting layer — see Future Work below.

### Bugs fixed in session 2
- `fetch_dfe_performance.py`: URN filter added to `save_to_sqlite()` — FK constraint was firing because KS2/KS4 covers all of England, not just London/Surrey.
- `fetch_supplementary_data.py`: Same URN filter added. Also fixed `filter_london_surrey()` — absence/exclusions files use `"State-funded primary"/"State-funded secondary"` rather than `"Primary"/"Secondary"`, causing 0-row output. Fixed with a regex strip before matching.

---

## Run Order (for a full rebuild from scratch)
```bash
cd "/root/my-vault/school selector"
rm ofsted_schools.db                        # only if rebuilding
venv/bin/python fetch_ofsted_data.py        # ~2 mins
venv/bin/python fetch_dfe_performance.py    # ~5 mins (large downloads already cached)
venv/bin/python fetch_supplementary_data.py # ~5 mins
```

---

## Key Technical Notes

### Ofsted CSV encoding
The Ofsted CSV uses **Windows-1252** encoding (not UTF-8). Already fixed in `fetch_ofsted_data.py` — uses `encoding="cp1252"`.

### Ofsted now uses OEIF framework
Ofsted changed their inspection framework. The grades in `judgements` are now:
- `overall_effectiveness`, `quality_of_education`, `behaviour_and_attitudes`
- `personal_development`, `leadership_and_management`
- `early_years_provision`, `sixth_form_provision`
- `safeguarding_effective`, `category_of_concern`
Old framework had different category names (e.g. "Achievement", "Curriculum and teaching").

### Progress 8 (KS4)
Not available for 2024/25 cohort due to COVID (no KS2 prior attainment data).
Most recent year with P8 = **2023/24** — that's what the script downloads.

### KS4 Destination Measures
School-level destination data (where pupils go after GCSEs) is **not available as a public bulk download**. Only national and LA-level data exists on EES. Decided not to include.

### FSM %
- `applications` table has `fsm_eligible_pct` — actual FSM % from the applications file ✅
- `primary_performance` and `secondary_performance` have `pct_disadvantaged` — FSM/Pupil Premium proxy

### Virtual environment
Always use `venv/bin/python` not system `python3` (system python is externally managed on this Ubuntu VM).

---

## Data Sources

| Dataset | Source URL | File |
|---------|-----------|------|
| Ofsted latest inspections | https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes | Auto-downloaded (monthly) |
| KS2 attainment 2024/25 | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/b361b4c3-21b9-46fd-9126-b8060c6a40e2/csv | Auto-downloaded |
| KS4 performance 2023/24 | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/c8f753ef-b76f-41a3-8949-13382e131054/csv | Auto-downloaded |
| Pupil absence 2023/24 | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/1ef1689a-070a-4e0b-9314-512db23a3cc9/csv | Auto-downloaded |
| Exclusions/suspensions 2023/24 | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/6ffc5087-5f61-47a1-9086-d1c374039d1b/csv | Auto-downloaded |
| Applications & offers 2024 | School-level file from EES (54MB, manually downloaded) | Already in data/ |

---

## Future Work (user mentioned)
- Historical Ofsted data (2005–2015 archive + monthly files from 2013–present) — user wants this later
- Possible: build a query/reporting layer on top of the database
