# School Selector — Handoff Notes 5
**Date**: 2026-03-01
**Branch**: gh-pages
**Status**: Full 5-step app working. Significant UI, styling, and logic improvements across all steps. Rightmove URL bug still outstanding (carried from HANDOFF_4).

---

## What Was Done This Session

### 1. Apple Design System
- Created `.streamlit/config.toml` with Apple colour palette (`#0071e3` blue, `#1d1d1f` text, `#f5f5f7` secondary bg)
- Injected comprehensive CSS in `app.py`: SF Pro font stack, pill buttons, 18px-radius cards, thin progress bar, metric label uppercase, clean input borders, caption colours, table styling
- **Bug fix**: removed `*` from font selector which was overriding Streamlit's icon fonts and rendering raw glyph names in expanders

### 2. Step 2 — LA Ranking Logic
- Added `_la_high_score_count(ks_keys)` — counts schools with `composite_score >= 60` per LA per relevant phase table, summed across phases
- Threshold rationale: `>=70` left City of London and Bexley/Havering with 0 schools in some phases; `>=60` gives full 33-LA coverage
- New weights: **35% commute + 30% avg quality + 35% high-score count** (was 50/50)
- Ranking caption and metric tile updated accordingly
- Constant `_HIGH_SCORE_THRESHOLD = 60` in `step2_la_select.py` for easy adjustment

### 3. Step 4 — School Cards
- Removed "Radius is fixed by the API and cannot be narrowed." from crime caption
- Added (then removed per feedback) admission type label on each card — helper `_phase_admission_type(ks_key)` remains in file but result is no longer displayed

### 4. Step 5 — Crime Contextualisation
- Removed the crime-by-category frequency table
- Top 2 most frequent crime types (by name and count) now woven into the caption alongside violent crime % and total
- "Low/Moderate/High/Very high" band definitions moved to `st.caption()` (small grey font) rather than `st.markdown()`

### 5. Step 5 — School Information Section
- New section added above Admissions: **address** (assembled from `STREET`, `LOCALITY`, `ADDRESS3`, `TOWN`, `POSTCODE` via `_school_details(urn)` lookup on schools table), **age range** (`AGELOW`–`AGEHIGH`), **school type**, **total pupils**, **free school meals %**, **EAL %**

### 6. Step 5 — Admissions Section
- Added standard vs in-year determination at top of Admissions section
- Logic accounts for **future KS stages**: a child in Year 4 looking at secondary schools now correctly shows "Standard admission for Year 7 in 2 years (deadline 31 Oct 2027)" rather than in-year
- Entry points: ks2 `apply_yg=-1` (Nursery year), ks4 `apply_yg=6` (Year 6), ks5 `apply_yg=11` (Year 11)
- Deadlines computed dynamically from `_academic_year_start()`
- Two tailored explanations of how **distance rules differ** between standard and in-year admission

### 7. Step 5 — Absence Metric Colour Fix
- `_delta()` returns `(delta_str, delta_colour)` but colour was previously discarded (`_`)
- Now passed as `delta_color=delta_colour` in all three metric sections (ks2, ks4, ks5)
- Absence now correctly shows **green when below London average** (lower = better)

### 8. Step 1 — KS Stages & Admission Reference Table
- Replaced single-line KS caption with an expander "Key stages & admission types explained" containing:
  - KS1/2/3/4/5 definitions
  - Reference table: year group → Standard/In-year → deadline note

### 9. Step 1 — Per-Phase Admission Info
- Replaced `_admission_type(yg)` (single result) with `_phase_admission_detail(ks_key, yg)` (per-phase)
- For a child with multiple phases in scope (e.g. Year 4 → both Primary and Secondary), each phase shows its own admission type and deadline on a separate line
- **Too-young children** (not yet school age): raw year group computed even below −1, synthetic KS2 phase generated, app proceeds to show primary school options
  - Formula: `raw_yg = (acad_start - birth_year - correction) - 4`
  - `years_until_application = −1 − raw_yg` (Nursery year is when application is made)
  - `deadline = ~15 Jan {acad_start + years_until + 1}`
- `children_ok` now checks `bool(c["phases"])` rather than `c["year_group"] is not None` — allows young children through
- Blocking warning "couldn't be resolved to a year group" removed

### 10. Deadline Consistency Fix
- Step 1 and Step 5 were computing different deadlines for a Jan 2024 child (Jan 2028 vs Jan 2029)
- Root cause: step 5 used `apply_yg=0` (Reception start) instead of `apply_yg=-1` (Nursery, when application is actually made)
- Fixed by changing ks2 `apply_yg` to `−1` in step 5's `_ENTRY` dict
- Both steps now agree: Jan 2024 child → **deadline ~15 Jan 2028** (for September 2028 Reception start)

---

## Outstanding Bug: Rightmove URL (carried from HANDOFF_4)

No progress made this session. See HANDOFF_4 for full history and next steps.

**Quick recap**: The Rightmove button in Step 5 doesn't land on correct results. Working URL format confirmed:
```
https://www.rightmove.co.uk/property-for-sale/find.html?searchLocation=N1C+4DB&useLocationIdentifier=true&locationIdentifier=POSTCODE%5E4554477&radius=0.5&_includeSSTC=on
```
Attempt 3 used the typeahead API to resolve postcode → numeric ID but is suspected to be failing silently. Next step: add `st.write(loc_id)` debug in step 5 to confirm whether `_resolve_location_identifier()` returns a value or None.

Relevant file: `utils/rightmove.py`

---

## Files Changed This Session

| File | Changes |
|---|---|
| `.streamlit/config.toml` | New — Apple theme colours |
| `app.py` | Apple CSS injection |
| `steps/step1_input.py` | KS expander, per-phase admission, too-young handling, children_ok fix |
| `steps/step2_la_select.py` | `_la_high_score_count`, new 35/30/35 weights |
| `steps/step4_shortlist.py` | Removed crime API radius note |
| `steps/step5_deepdive.py` | Crime context, school info section, admissions standard/in-year, delta_color fix, deadline consistency fix |

---

## Key Implementation Notes (New)

### Admission type logic
- **Step 1**: `_phase_admission_detail(ks_key, yg)` in `step1_input.py` — one call per phase per child
- **Step 5**: `_ENTRY` dict with `apply_yg`, `max_in_phase`, `applying_for`, `deadline_fmt` lambda
- Both use `acad_start = year if month >= 9 else year - 1`
- KS2 `apply_yg = −1` (application at Nursery year, year BEFORE Reception starts)

### Score threshold (Step 2)
- `_HIGH_SCORE_THRESHOLD = 60` in `step2_la_select.py`
- Queries `metrics_ks2/ks4/ks5` directly (not `metrics_la`), counting `COUNT(DISTINCT URN)` per LANAME
- Summed across relevant phases; consistent because all LAs see the same ks_keys

### Absence delta colour
- `_delta(val, avg, higher_is_better=False, fmt)` returns `("−2.0 vs London avg", "inverse")` when school is above average (bad)
- Must pass `delta_color=delta_colour` to `st.metric()` — was previously discarded

---

## Running the App

```bash
cd /home/claude/my-vault/london_school_stats
source venv_app/bin/activate
streamlit run app.py
```

Note: `venv/` and `venv2/` are broken. Use `venv_app/` only.
