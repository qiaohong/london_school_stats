# School Selector — Handoff Notes 4
**Date**: 2026-03-01
**Branch**: gh-pages
**Status**: Full 5-step Streamlit app live. iterate_note_mar1 changes applied and pushed. One outstanding bug: Rightmove URL still broken.

---

## What Was Done This Session

### iterate_note_mar1.md — All 5 items implemented and pushed

| Item | Status |
|---|---|
| Step 1: default postcode `N1C 4DB` | ✅ Done |
| Step 1: tech company postcode table in expander | ✅ Done |
| Step 1: flexible commute = +20% of limit (not flat +20 min) | ✅ Done |
| Step 2: ranking = 50% commute + 50% school quality (from `metrics_la`) | ✅ Done |
| Step 3: remove religion selector (all faiths always included) | ✅ Done |
| Step 3: add DfE-sourced explanations for each filter | ✅ Done |
| Step 4: Ofsted date format fixed (DD-MM-YYYY → Mon YYYY) | ✅ Done |
| Step 4: source captions for house price and crime data | ✅ Done |
| Step 5: Rightmove URL fixed (find.html + OUTCODE^{outcode}) | ⚠️ Partially — see below |

---

## Outstanding Bug: Rightmove URL

### Symptoms
The Rightmove button in Step 5 still does not land on the correct search results page. Three attempts made, all unsuccessful.

### Attempts so far

**Attempt 1**: `/in-{outcode}.html` — redirected to homepage, ignored params.

**Attempt 2**: `find.html?locationIdentifier=OUTCODE^{outcode}` — `OUTCODE` prefix with text outcode is not a valid Rightmove identifier format.

**Attempt 3** (2026-03-01): Rewrote `utils/rightmove.py` to call Rightmove's typeahead API (`api.rightmove.co.uk/api/typeAhead/v1/autocomplete`) to resolve postcode → numeric ID, then build `POSTCODE%5E{numeric_id}` URL. URL format was confirmed correct from a real browser URL (`N1C 4DB` → `POSTCODE^4554477`). Still not working — suspected the typeahead API call is failing silently and the fallback bare-`searchLocation` URL is being used instead.

### What a working URL looks like (captured from browser)
```
https://www.rightmove.co.uk/property-for-sale/find.html?searchLocation=N1C+4DB&useLocationIdentifier=true&locationIdentifier=POSTCODE%5E4554477&radius=0.5&_includeSSTC=on
```

### Next steps
1. **Check if typeahead API call is actually succeeding** — add a `st.write(loc_id)` debug line in step5 to print the resolved `locationIdentifier`. If it's `None`, the API is failing.
2. **If API fails**: the `api.rightmove.co.uk` host may block non-browser requests. Try adding more browser-like headers (`Accept`, `Referer`, `Accept-Language`) or use a different endpoint.
3. **Alternative**: hardcode a lookup table of London postcode → numeric ID (scraped once), bypassing the live API entirely.

### Relevant file
`utils/rightmove.py` — `_resolve_location_identifier()` and `build_url()`.

---

## App Architecture Summary

```
app.py                      — entry point, step router
steps/
  step1_input.py            — postcode, commute prefs, children DOBs
  step2_la_select.py        — heuristic commute + quality ranking, borough selection
  step3_criteria.py         — Ofsted, school type, admissions, gender, score floor
  step4_shortlist.py        — filtered school cards with neighbourhood data
  step5_deepdive.py         — full metrics, comparison, Rightmove link
utils/
  age_stage.py              — DOB → year group → relevant phases (ks2/ks4/ks5)
  commute.py                — heuristic commute estimate via LA centroid + transit speed
  db.py                     — query_schools(), Ofsted dedup subquery
  neighbourhood.py          — postcodes.io geocoding, police API crime, house prices
  rightmove.py              — Rightmove URL builder (⚠️ bug outstanding)
data/
  la_commute_profile.json   — 33 LA profiles: centroid, zones, transit lines, character
  la_house_prices.json      — 2024 median house price per borough (Land Registry)
  la_admissions_urls.json   — admissions page URLs for all 33 boroughs
schools.db                  — SQLite: schools, metrics_ks2/ks4/ks5, metrics_la, etc.
```

---

## Key Implementation Notes

### Commute estimation (heuristic, no live API)
Speed constants in `utils/commute.py`:
- Tube: 0.38 km/min, DLR: 0.34, Overground: 0.30, Rail: 0.28
- Formula: `10 + dist_km / speed` (with ±10–20% variance for min/max)
- Filters LAs where `commute_min <= commute_limit + flex_minutes`

### Borough ranking (Step 2)
```python
commute_score = 1 - (mid - min_mid) / (max_mid - min_mid + 1)
quality_score = (q - min_quality) / quality_range
combined = 0.5 * commute_score + 0.5 * quality_score
```
`q` = avg_composite from `metrics_la` averaged across relevant phases.

### Ofsted dedup (schools table has 3 rows/URN across years)
```sql
LEFT JOIN (
  SELECT URN, OFSTEDRATING, OFSTEDLASTINSP
  FROM schools WHERE OFSTEDRATING IS NOT NULL
  GROUP BY URN HAVING MAX(academic_year)
) s ON m.URN = s.URN
```

### Crime data centroid
School's postcode geocoded via postcodes.io. Radius ~1 mile (fixed by police API, cannot be narrowed). Data from `data.police.uk/api/crimes-street/all-crime`.

### Rightmove radius logic
`cutoff_km * 1.2` (20% buffer) converted to miles, then snapped to nearest Rightmove-supported radius value `[0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, ...]`.

---

## Running the App

```bash
cd /home/claude/my-vault/london_school_stats
source venv_app/bin/activate
streamlit run app.py
```

Note: `venv/` and `venv2/` are broken (bad interpreter paths). Use `venv_app/`.

---

## Recent Commits

```
28047dc Fix Rightmove URL: keep literal ^ in locationIdentifier
0f4d80b Apply iterate_note_mar1 fixes across all steps
52e4b3f Add Streamlit school selector app (Steps 1–5) and documentation
```
