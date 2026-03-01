# Plan 4 — Architecture & Tech Stack Decision

This document covers the architectural foundation for the new interactive school-selector app described in `overall_ui_flow.md`. The existing project is a static HTML file on GitHub Pages. The new flow requires real-time APIs and multi-step state, which means a different architecture.

---

## 1. Why we need a new architecture

The static `report.html` site cannot support:
- Server-side commute time calculations (needs API keys, CORS restrictions)
- Multi-step stateful wizard UI
- Dynamic neighbourhood data lookups per school

We need a backend (or a rich client-side framework with API calls).

---

## 2. Architecture Options

### Option A — Streamlit (Recommended)
- Python only, consistent with existing codebase
- Native support for multi-step wizard UIs (using `st.session_state`)
- Easy deployment on **Streamlit Community Cloud** (free tier)
- Can reuse `schools.db` SQLite database directly
- Built-in map support (via `st.map` or `pydeck`)
- No separate frontend/backend split
- **Cons**: Less visual control than custom HTML; some layout limitations

### Option B — FastAPI backend + Vanilla JS frontend
- FastAPI serves a JSON API; frontend is a new HTML/JS page
- More control over UI but significantly more code
- Harder to deploy (needs a server, not just GitHub Pages)
- **Cons**: More complex, two codebases

### Option C — Client-side only (extend current report.html)
- All API calls from JavaScript
- Problem: commute time APIs (TfL, Google) require server-side keys for CORS safety
- Only viable if we use APIs with no-key/public endpoints
- **Cons**: Security risk for API keys, limited to CORS-permissive APIs

### Decision: **Streamlit (Option A)**
Rationale: fastest to build, easiest to deploy, Python consistent with data pipeline, stateful wizard UX is natural in Streamlit.

---

## 3. New File Structure

```
london_school_stats/
├── app.py                  ← NEW: main Streamlit app (entry point)
├── steps/
│   ├── step1_input.py      ← postcode, commute, child DOB
│   ├── step2_la_select.py  ← LA recommendation, commute filtering
│   ├── step3_criteria.py   ← school preference inputs
│   ├── step4_shortlist.py  ← school list + neighbourhood data
│   └── step5_deepdive.py   ← single school detail + Rightmove URL
├── utils/
│   ├── commute.py          ← commute time API wrapper
│   ├── neighbourhood.py    ← housing, crime, pollution data
│   ├── rightmove.py        ← Rightmove URL builder
│   ├── age_stage.py        ← child DOB → year group → school stages
│   └── db.py               ← SQLite query helpers
├── schools.db              ← existing DB (gitignored)
├── generate_report.py      ← existing static site generator (keep)
├── report.html             ← existing static site (keep on gh-pages)
└── requirements.txt        ← add streamlit, requests, etc.
```

---

## 4. Rightmove URL Format

### Research Findings

Rightmove supports a URL-based property search. The key parameters:

**Base URL:**
```
https://www.rightmove.co.uk/property-for-sale/find.html
```

**Key query parameters:**
| Parameter | Description | Example |
|---|---|---|
| `locationIdentifier` | Area identifier (see below) | `OUTCODE%5E87156` |
| `radius` | Miles from centre | `0.25`, `0.5`, `1.0`, `3.0` |
| `sortType` | 6 = distance, 2 = newest | `6` |
| `maxPrice` | Max price filter | `500000` |
| `minBedrooms` | Min bedrooms | `3` |
| `propertyTypes` | Comma-separated types | `detached,semi-detached` |
| `includeSSTC` | Include sold STC | `false` |

**Location Identifier format:**
Rightmove uses internal IDs. The format is `TYPE^ID` URL-encoded as `TYPE%5EID`.
- `OUTCODE^{id}` — e.g. SW1A, E1
- `STATION^{id}` — near a station
- `POSTCODE^{id}` — specific postcode

**Problem:** The numeric ID is internal and not easily known from a postcode alone.

**Workaround — use their autocomplete API (no key required):**
```
GET https://api.rightmove.co.uk/api/typeAhead/uknoauth?query={postcode}&numberOfSuggestions=1
```
This returns the `locationIdentifier` for a given postcode or area. We can call this at runtime.

**Fallback — simpler outcode search:**
```
https://www.rightmove.co.uk/property-for-sale/in-{outcode}.html?radius={miles}
```
e.g. `https://www.rightmove.co.uk/property-for-sale/in-e1.html?radius=0.5`
This works without an ID lookup but is less precise.

### Implementation Plan for Step 5

1. Take the school's postcode from the DB
2. Extract the outcode (first part, e.g. `E1` from `E1 6RF`)
3. Optionally call Rightmove autocomplete API to get location ID for postcode-level precision
4. Use admission distance cutoff (if known) or default to 0.5 miles as radius
5. Construct URL with optional price/bedroom filters (passed from user preferences in Step 3)
6. Open URL via `st.link_button` in Streamlit or render as `<a href>` in HTML

**Example URL for school at E1 6RF, admission distance 0.3 miles:**
```
https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=POSTCODE%5E{id}&radius=0.5&sortType=6&maxPrice=500000
```

---

## 5. Deployment Plan

1. Add `streamlit` to `requirements.txt`
2. Create `app.py` scaffold with session state
3. Deploy to **Streamlit Community Cloud** (connect to GitHub repo, point to `app.py`)
4. Keep existing `gh-pages` branch + `report.html` unchanged as companion reference tool

---

## 6. Build Sequence

The recommended order (each phase must complete before the next):

1. `plan_5_input_stages.md` — Step 1 + 2 (input + LA selection)
2. `plan_6_criteria_shortlist.md` — Step 3 + 4 (criteria + shortlist)
3. `plan_7_deep_dive.md` — Step 5 (deep dive + Rightmove)
4. Polish, deploy, test end-to-end
