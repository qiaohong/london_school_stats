# Plan 6 — Step 3 & 4: School Criteria + Neighbourhood Shortlist

---

## Step 3 — School Criteria Collection

### Inputs to collect (with defaults)

| Criterion | Input type | Default | Notes |
|---|---|---|---|
| School phase | Auto-set from Step 1 | From child DOB | Can be overridden |
| Ofsted rating | Multi-select checkboxes | Outstanding + Good | Options: O, G, RI, Inadequate |
| School type | Multi-select | All selected | Comprehensive, Academy, Grammar, Faith, Free |
| Admissions type | Single select | Non-selective | Selective / Non-selective / Any |
| Composite score | Slider, min | 50 | 0–100, from existing DB |
| Max class size / school size | Optional dropdown | Any | Small (<600), Medium, Large (>1200) |
| Faith preference | Checkbox | No preference | CoE, Catholic, Jewish, Muslim, Other, None |
| Single-sex preference | Dropdown | Any | Boys, Girls, Mixed |

### Explanations to show in UI
Each criterion should have an inline "?" tooltip or expander:
- Ofsted: "Ofsted inspects schools roughly every 4 years. Outstanding schools are rare (~6% of London schools)."
- Composite score: "Our score combines attainment, progress, attendance and destinations. 50 = London average."
- Selective: "Grammar schools and some faith schools select on ability/faith. Non-selective schools take all abilities."

---

## Step 4 — School Shortlist with Neighbourhood Data

### 4a. School Filtering
Apply Step 3 criteria to `metrics_ks2`/`metrics_ks4`/`metrics_ks5` tables in `schools.db`, filtered to the selected LAs from Step 2.

Sort options:
- Composite score (default)
- Distance from work postcode (using geocoded school coords already in DB)
- Ofsted rating
- Estimated admission distance (if available)

Cap: top 20 schools per phase.

### 4b. Neighbourhood Data per School

For each school in the shortlist, show a summary of local neighbourhood characteristics. Data is fetched at runtime via free public APIs.

---

## Neighbourhood Data Sources — Availability Research

### 1. Housing Prices

**Source:** HM Land Registry UK House Price Index
- **API:** `https://landregistry.data.gov.uk/linked-data/api/statistics`
- **Coverage:** All England and Wales, by local authority or postcode district
- **Frequency:** Monthly updates, available from 1995
- **Key metric:** Average/median sale price for postcode district (e.g. E1, SW9)
- **No API key required**
- **Granularity:** Postcode district (outcode level), not full postcode
- **Implementation:** Call at app start, cache results for selected LAs

**Fallback:** ONS HPSSA dataset (house price statistics for small areas), CSV download.

**What to display:** median sale price for school's outcode; price change % over last 2 years

---

### 2. Crime

**Source:** data.police.uk API
- **API:** `https://data.police.uk/api/crimes-at-location?lat={lat}&lng={lng}&date=YYYY-MM`
- **Coverage:** England and Wales, updated monthly
- **No API key required**
- **Returns:** List of crimes with category, location, date
- **Rate limit:** ~429 calls/min (generous for our use)
- **Key categories to highlight:** violent-crime, burglary, anti-social-behaviour, vehicle-crime

**Implementation:**
- Use school's geocoded lat/lng (already in `schools.db`)
- Fetch last 12 months, count by category
- Display: crime density score (crimes per km²) and breakdown bar

**Limitation:** Returns crimes within ~1 mile of a point, not strictly per postcode. Will need to normalise.

---

### 3. Air Pollution

**Source A:** London Air Quality Network (LAQN) — best for London
- **API:** `https://api.erg.ic.ac.uk/AirQuality/Annual/MonitoringObjective/GroupName=London/Json`
- **Coverage:** ~130 monitoring stations across London
- **No key required**
- **Metric:** Annual mean NO₂, PM2.5, PM10 (µg/m³)
- **Limitation:** Sparse coverage — not all school postcodes have a nearby station

**Source B:** DEFRA UK-AIR mapped data
- Downloadable CSV of modelled NO₂/PM2.5 at 1km grid level for all of England
- **URL:** `https://uk-air.defra.gov.uk/data/pcm-data`
- **No key required**
- **Implementation:** Download once, store as lookup table (postcode → pollution values)
- Recommended approach for reliability: pre-join this data with school postcodes at build time, store in `schools.db`

**What to display:** NO₂ annual mean (µg/m³) with a colour-coded indicator (green <25, amber 25–40, red >40). WHO limit = 10 µg/m³; UK legal limit = 40 µg/m³.

---

### 4. Housing Stock

**Source:** Census 2021 (ONS)
- **Tables:** TS044 (tenure), TS053 (dwelling type: detached/semi/terraced/flat)
- **Coverage:** All of England and Wales at LSOA level (~1,600 households)
- **No key required**
- **Download:** ONS bulk CSV download by LSOA
- **Implementation:** Pre-join at build time, store in `schools.db` as postcode → LSOA → tenure/type breakdown

**What to display:**
- % owner-occupied vs renting (signals stability/community feel)
- % flats vs houses (important for families)
- Average number of rooms (proxy for space)

**Limitation:** 2021 data; some areas have changed since then.

---

### 4c. Combined Shortlist Display

For each school card, show:

```
┌─────────────────────────────────────────────────────┐
│ School Name                          [Phase] [Ofsted]│
│ Borough · School type                                │
│                                                      │
│ Composite score: 78/100  │  Distance: 1.2 km        │
│                                                      │
│ NEIGHBOURHOOD                                        │
│ Avg house price:  £485,000  (+4% / 2yr)             │
│ Crime index:      Low  ████░░░░  (45th %ile London) │
│ Air quality NO₂:  32 µg/m³  (Amber)                │
│ Housing stock:    62% houses · 51% owner-occupied   │
│                                                      │
│ [Add to compare]  [View details →]                  │
└─────────────────────────────────────────────────────┘
```

### 4d. Build-time vs Runtime

| Data | When fetched | Storage |
|---|---|---|
| School metrics | Build time | `schools.db` |
| School geocodes | Build time | `schools.db` |
| Pollution (DEFRA) | Build time | `schools.db` |
| Housing stock (Census) | Build time | `schools.db` |
| Crime | Runtime via API | Cached per session |
| House prices | Runtime via Land Registry API | Cached per session |

---

## Files to Create

```
utils/neighbourhood.py      ← housing, crime, pollution data fetchers
utils/cache.py              ← simple TTL cache for runtime API calls
data/defra_pollution.csv    ← DEFRA modelled NO₂/PM2.5 by 1km grid (download once)
data/census_housing.csv     ← ONS Census 2021 TS044/TS053 (download once)
steps/step3_criteria.py     ← Streamlit UI for school criteria
steps/step4_shortlist.py    ← Streamlit UI for shortlist + neighbourhood cards
```

Also update `load_data.py` or create `load_neighbourhood.py` to pre-join pollution and housing stock into `schools.db` at build time.

---

## Open Questions / Risks

- **Crime API latency:** 20 schools × 1 API call = ~3 seconds. Use async calls or a loading spinner.
- **Housing price postcode district lookup:** Land Registry API may not have all outcodes — fallback to LA-level average.
- **DEFRA pollution data format:** 1km grid needs mapping to school postcodes — test coverage before committing to this source.
- **Census 2021 LSOA mapping:** Requires postcode → LSOA lookup table (available from ONS, ~2MB CSV).
