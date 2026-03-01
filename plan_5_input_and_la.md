# Plan 5 — Step 1 & 2: Input Collection + LA Selection

Covers the first two steps of the `overall_ui_flow.md` wizard.

---

## Step 1 — Input Collection

### 1a. Work Postcode
- Text input, validated via `postcodes.io` (free, no key)
- Full postcode preferred (e.g. `EC2A 4PX`), fall back to outward code
- Store resolved lat/lng in session state for commute estimation

### 1b. Commute Time
- Numeric input: desired commute time in minutes (default 30)
- Flexibility toggle: "Strict" (no buffer) / "Flexible" (add 20 min buffer)
  - If flexible: effective limit = input + 20 min

### 1c. Children's Birth Date(s)
- Allow up to 3 children
- Input: birth month + year (not full date, for privacy)
- Age → Year Group calculation (see below)

---

## Child Age → Year Group → School Stage Logic

**Year group formula (England):**
```
academic_year_start = September
school_year = current_calendar_year - birth_year - 1 (if before Sept) or - birth_year (if Sept+)
year_group = school_year - 4   # Reception = age 5, so YG = age - 4 in Sept
```

**School stage mapping:**
| Year Group | Stage | Phase |
|---|---|---|
| Reception–Y6 | Primary | KS1/KS2 |
| Y7–Y11 | Secondary | KS3/KS4 |
| Y12–Y13 | Sixth Form | KS5 |

**Look-ahead logic:**
- Show stages relevant to current year group **AND** next 3 year groups
- If child is Y5: show Primary (current), Secondary (in 2 years)
- If child is Y4: show Primary only (Secondary is 4 years away — out of window)
- If child is Y10: show Secondary (current), Sixth Form (in 2 years)

**Key transitions to surface:**
- Y6→Y7 (Primary to Secondary): apply in Oct–Nov of Y6
- Y11→Y12 (Secondary to Sixth Form): apply Jan of Y11

---

## Step 2 — LA Recommendation

### 2a. Commute Estimation Approach: Heuristics (no real-time API)

Rather than calling a live commute API, we precompute a **commute score** per LA using static heuristics. This avoids API keys, latency, and cost.

**Heuristic model:**

Each LA is pre-tagged with:
- `tube_zones`: list of TfL zones covered (1–6)
- `mainlines`: rail lines serving the LA (e.g. Elizabeth line, Overground, Victoria)
- `inner_london`: boolean (within zone 2)
- `centroid_km`: approximate km from Charing Cross (central reference)

**Commute time estimate to a work postcode:**
1. Resolve work postcode → lat/lng → determine which tube/rail zone it falls in
2. Look up LA's nearest tube zones and connections
3. Apply a lookup table:

| LA zone → Work zone | Estimated commute |
|---|---|
| Same zone | 15–25 min |
| Adjacent zone | 20–35 min |
| 2 zones away | 30–50 min |
| 3+ zones away | 45–70 min |
| No direct rail connection | +15 min penalty |

4. If LA centroid is >5km from nearest tube station, add +10 min walking penalty

**Implementation:**
- Create `data/la_commute_profile.json` with static per-LA metadata (33 London LAs)
- Function: `estimate_commute(la_id, work_lat, work_lng) → (min_min, max_min)`
- Filter LAs where `max_min <= effective_limit`
- Rank by `min_min` ascending

### 2b. LA Rationale

For each shortlisted LA (target: top 3), auto-generate a brief rationale:
```
"{LA name} is well-connected via the {line(s)}, with typical commute times of
{min}–{max} minutes from {work postcode area}. It spans TfL zones {zones}."
```
Also add one sentence of character: inner/outer London, green space, housing character (can be hardcoded per LA for MVP).

### 2c. User Confirmation
- Show top 3 recommended LAs with rationale
- Checkboxes to include/exclude
- Option to add other LAs manually (from a full dropdown of 33 boroughs)
- Button: "Confirm selection → Next"

---

## Data Required for This Step

| Data | Source | Notes |
|---|---|---|
| LA commute profiles | Manually curated JSON | One-off, stable |
| Work postcode → lat/lng | postcodes.io (free, no key) | Already used in existing site |
| TfL zone boundaries | TfL open data (GeoJSON) | Can download once, embed in app |
| LA boundaries (optional) | ONS Open Geography Portal | GeoJSON if needed for map display |

---

## Files to Create

```
utils/age_stage.py          ← child DOB → year groups → stages
utils/commute.py            ← LA commute heuristic estimator
data/la_commute_profile.json ← static LA metadata (zones, lines, centroid, character)
steps/step1_input.py        ← Streamlit UI for input collection
steps/step2_la_select.py    ← Streamlit UI for LA selection
```

---

## Open Questions

- Should we show a map of the recommended LAs? (Nice to have, not critical for MVP)
- Maximum number of LAs to shortlist: 3 recommended, but allow up to 5 selected total
