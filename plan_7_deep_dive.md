# Plan 7 — Step 5: School Deep Dive + Rightmove Integration

---

## Overview

When the user selects a single school from the Step 4 shortlist, this screen shows:
1. Full school metrics and Ofsted report summary
2. Admission criteria and historical cut-off distances
3. A Rightmove link pre-configured to search near the school

---

## 5a. School Metrics Panel

Pull from existing `schools.db`:
- All composite score components (progress, attainment, absence, destinations)
- Ofsted rating + year of last inspection
- School type, admissions policy, number on roll
- Website URL (if in dataset)

Compare against:
- Borough average (from `metrics_la`)
- London average (computed)

Display as a bar chart or table showing school vs borough vs London.

---

## 5b. Admission Criteria + Cut-off Distances

### Data Source

The `gemini_london_admission_data.md` file catalogues all 27 London boroughs' admission outcome pages. This is the starting point for sourcing cut-off distances.

**What we want per school:**
- Admission distance cutoff: last year offered distance (straight-line km/miles)
- Trend: last 3 years' distances (is it getting tighter or looser?)
- Oversubscription criteria: priority order (e.g. looked after children → sibling → distance)
- Any banding system (ability bands, faith criteria)

### Approach — Phased Plan

**Phase A (MVP): Manually curated per-LA table**
- Create `data/admission_cutoffs.json`: per-school, last 3 years' cut-off distances
- Source: visit each LA's page from the gemini file, extract the table
- Priority LAs to collect first (highest user value):
  1. Haringey — direct URL to cut-off data already known from gemini file
  2. Islington — cut-off distance tables 2023–2025
  3. Camden — secondary offer distances
  4. Ealing — on-time offers PDF 2025
  5. Hackney — cut-off distance summary 2018–2025
- This covers inner North and West London; most likely LAs for a city-centre commuter

**Phase B: Semi-automated PDF/HTML parser**
- For LAs publishing structured HTML tables: use `requests` + `BeautifulSoup` to scrape
- For PDFs: use `pdfplumber` to extract tables
- Not all LAs will be automatable — some may need manual copy-paste
- Build one parser per LA that publishes PDFs, share common pattern for HTML tables

**Key notes from gemini file:**
- Most boroughs measure **straight-line** distance (not walking/road)
- Banding exceptions: Greenwich, Tower Hamlets, Wandsworth — admission distances are per band
- Cut-off distances stretch further after National Offer Day as places are declined
- Published distances = "last child offered on National Offer Day", not final allocation

**Data schema for `admission_cutoffs.json`:**
```json
{
  "URN123456": {
    "school_name": "Example School",
    "la_name": "Haringey",
    "phase": "KS4",
    "cutoffs": [
      {"year": "2024-25", "distance_km": 0.45, "notes": ""},
      {"year": "2023-24", "distance_km": 0.52, "notes": ""},
      {"year": "2022-23", "distance_km": 0.60, "notes": ""}
    ],
    "oversubscription_criteria": "LAC > sibling > distance",
    "banded": false,
    "source_url": "https://haringey.gov.uk/..."
  }
}
```

---

## 5c. Rightmove URL Builder

### URL Format

**Recommended approach: outcode search with radius**
```
https://www.rightmove.co.uk/property-for-sale/in-{outcode}.html?radius={miles}&maxPrice={price}&minBedrooms={beds}
```

Outcode = first part of school postcode (e.g. `N8` from `N8 9DP`).

Example:
```
https://www.rightmove.co.uk/property-for-sale/in-n8.html?radius=0.5&maxPrice=600000&minBedrooms=3
```

**Enhanced approach: postcode-level search (more precise)**
Use Rightmove's public autocomplete API to get their internal location ID:
```
GET https://api.rightmove.co.uk/api/typeAhead/uknoauth?query={postcode}&numberOfSuggestions=1
```
Returns JSON with `locationIdentifier` (e.g. `POSTCODE^12345`).

Then build:
```
https://www.rightmove.co.uk/property-for-sale/find.html
  ?locationIdentifier=POSTCODE%5E12345
  &radius={miles}
  &maxPrice={price}
  &minBedrooms={beds}
  &sortType=6
  &propertyTypes=
  &includeSSTC=false
```

**Radius selection logic:**
- If admission cut-off distance is known: use that distance + 10% buffer, in miles
- If not known: use 0.5 miles default (roughly 0.8 km, typical for urban London)
- Convert km → miles: `miles = km * 0.621371`
- Round to nearest Rightmove-supported radius: 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0 miles

**User-configurable parameters (pick up from Step 3 criteria):**
- Max price (optional)
- Min bedrooms (optional)
- Property type (optional)

### Presentation

In the Streamlit app:
```python
st.link_button(
    "Search properties near this school on Rightmove →",
    url=rightmove_url,
    type="primary"
)
```

Also display a note:
> "Searching within {X} miles of {school postcode}. This radius is based on last year's admission cut-off distance of {Y} km."

---

## 5d. School Planning Documents (Haringey-first)

The HANDOFF_3.md mentioned Haringey as having a school planning document with future predictions of school places.

**Haringey-specific:**
- URL: `https://haringey.gov.uk/schools-learning/schools/school-admissions/how-school-place-offers-were-made/cutoff-distance-school-last-child-offered-place`
- Also search: "Haringey school place planning report" — typically published annually by the council
- Contains: projected pupil numbers by year group, planned new school places, surplus/deficit forecasts
- Parse: school places by year × school name table

**How to use in app (Step 4/5):**
- Flag schools where surplus is forecast (easier to get in future years)
- Flag schools where deficit is forecast (may become harder — apply early)
- Show trend arrow: surplus shrinking → school becoming more competitive

**For other LAs:** Only collect planning documents where explicitly available. Haringey first, then Camden and Islington (Inner North London priority).

---

## Files to Create / Modify

```
utils/rightmove.py              ← URL builder function
utils/admission_data.py         ← load + query admission_cutoffs.json
data/admission_cutoffs.json     ← manually curated, start with 5 priority LAs
data/la_planning_reports/       ← extracted school places data from planning docs
  haringey_school_places.json
steps/step5_deepdive.py         ← Streamlit UI for school detail view
```

---

## Build Order for Step 5

1. Implement `rightmove.py` URL builder (quick, no external dependency)
2. Manually collect Haringey + 4 other LA cut-off distances → `admission_cutoffs.json`
3. Build `step5_deepdive.py` UI (metrics + Rightmove link works without admission data)
4. Add admission data panel once `admission_cutoffs.json` has enough coverage
5. Add school planning surplus/deficit flags (Haringey first)
