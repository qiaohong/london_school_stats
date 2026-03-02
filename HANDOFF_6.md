# School Selector — Handoff Notes 6
**Date**: 2026-03-02
**Branch**: gh-pages
**Status**: Full 6-step app working. Custom score builder with binary top-10% flag added. Rightmove URL bug still outstanding (carried from HANDOFF_4).

---

## What Was Done This Session

### Context: App Restructure (completed this session, carried from last)
The app was restructured from 5 steps to 6, inserting a new "Build your score" step between input and LA selection. The new step mapping:

| UI Step | File | Role |
|---|---|---|
| Step 1 | `steps/step1_input.py` | Postcode, 1 child, commute |
| Step 2 | `steps/step2_score_weights.py` | Custom composite score builder (**NEW**) |
| Step 3 | `steps/step2_la_select.py` | Borough recommendation + selection |
| Step 4 | `steps/step3_criteria.py` | School filters |
| Step 5 | `steps/step4_shortlist.py` | School cards + neighbourhood data |
| Step 6 | `steps/step5_deepdive.py` | Full school detail |

### 1. Step 2 — Binary Top-10% Flag (new feature)
For each attribute in the score builder, the user can now choose between two scoring modes:

- **Numeric score** (default): school is scored on a normalised [0,1] scale based on its position in the London-wide min/max range
- **Binary (top 10% only)**: school scores 1.0 if it's in the top 10% of London schools for that attribute, 0.0 otherwise

The top-10% threshold is shown inline: e.g. *"Binary (top 10% only — ≥ 0.88)"* for Progress 8. This lets users build a strict quality filter ("only shortlist schools in the top 10% for Progress 8") alongside continuous attributes.

**Implementation:**
- `utils/score_config.py`: added `fetch_top10_thresholds(ks_key, field_keys)` — computes p10 (10th percentile) and p90 (90th percentile) from the metrics table using SQLite ORDER BY + OFFSET
- `steps/step2_score_weights.py`: loads thresholds for all ks_keys, cached in `_london_top10_{ks_key}`. Each attribute card shows threshold and a "Scoring mode" radio. Saves `score_weight_binary: dict[str, bool]` to session state.
- `steps/step4_shortlist.py` (`_apply_custom_score`): if `binary_flags.get(key)`, uses p90 (higher-is-better) or p10 (lower-is-better) threshold; norm = 1.0 or 0.0. Direction inversion NOT applied for binary (already direction-aware).
- `steps/step2_la_select.py` (`_la_custom_quality`): same binary logic for LA ranking.
- `steps/step2_score_weights.py` (`_all_london_scores`): same binary logic for distribution chart.

**Cache key:** top10 caches are keyed `_london_top10_{ks_key}`. Cleared alongside `_london_bounds_*` when shortlist criteria change.

### 2. Step 4 — Change Boroughs Button
Added a "Change boroughs" button to the right of the borough caption in `step3_criteria.py`. Navigates back to Step 3 (`st.session_state.step = 3`). Uses `st.columns([4, 1])` layout with caption on left, button on right.

### 3. Step 6 — Legacy Borough Comparison Removed
The "Borough comparison" expanders in `_section_metrics_ks2`, `_section_metrics_ks4` showed hardcoded system metrics (composite avg, Progress 8 avg, absence avg). These are now **hidden when `score_weights` is set** in session state, since `_section_custom_score` already shows per-attribute borough averages for each variable the user chose. When no custom score, the expanders remain visible as before.

### 4. Deadline Bug Investigation — Resolved (Not a Bug)
User reported: "Jan 2016 child shows Oct 2026 deadline for Year 7, should be Oct 2027."

Traced through `utils/age_stage.py`:
- `academic_start = 2025` (March 2026, month < 9)
- `age_at_sept = 2025 - 2016 = 9`, no correction (Jan not > Aug)
- `year_group = 9 - 4 = 5` → Year 5 ✓

A Jan 2016 child is correctly in Year 5 in 2025-26. They enter Year 6 in Sep 2026, apply for Year 7 in Oct 2026 (deadline), for Sep 2027 entry. **Oct 2026 is correct.** Oct 2027 would only be correct for a Year 4 child.

---

## Outstanding Bug: Rightmove URL (carried from HANDOFF_4)

No progress made this session. See HANDOFF_4 for full history.

**Quick recap**: The Rightmove button in Step 6 doesn't land on correct results. Working URL format:
```
https://www.rightmove.co.uk/property-for-sale/find.html?searchLocation=N1C+4DB&useLocationIdentifier=true&locationIdentifier=POSTCODE%5E4554477&radius=0.5&_includeSSTC=on
```
Next step: add `st.write(loc_id)` debug in Step 6 to confirm whether `_resolve_location_identifier()` returns a value or None.

Relevant file: `utils/rightmove.py`

---

## Files Changed This Session

| File | Changes |
|---|---|
| `utils/score_config.py` | Added `fetch_top10_thresholds()` |
| `steps/step2_score_weights.py` | Binary flag UI, threshold display, updated `_all_london_scores` |
| `steps/step4_shortlist.py` | Binary flag in `_apply_custom_score`, import `fetch_top10_thresholds`, clear top10 cache |
| `steps/step2_la_select.py` | Binary flag in `_la_custom_quality`, import `fetch_top10_thresholds` |
| `steps/step3_criteria.py` | "Change boroughs" button |
| `steps/step5_deepdive.py` | Hide legacy borough comparison when custom score active |

---

## Key Implementation Notes

### Binary flag scoring
- `score_weight_binary: dict[str, bool]` stored in session state
- For binary attribute, norm computed as 1.0/0.0 using p90 (if higher_is_better) or p10 (if lower_is_better) threshold
- Direction inversion (`if directions.get(key) is False: norm = 1.0 - norm`) is **skipped** for binary attributes — the threshold selection already accounts for direction
- If `val is None`: norm = 0.0 (not 0.5 as in numeric mode) — conservative; binary mode is a strict qualifier

### Top-10% threshold computation
- `fetch_top10_thresholds(ks_key, field_keys)` returns `{field_key: (p10, p90)}`
- Uses `SELECT {key} FROM {table} WHERE {key} IS NOT NULL ORDER BY {key} LIMIT 1 OFFSET {idx}`
- p10_offset = `int(n * 0.10) - 1`, p90_offset = `int(n * 0.90) - 1` (clamped to 0)

### Session state keys added
- `score_weight_binary: dict[str, bool]` — per-attribute binary flag
- `_london_top10_{ks_key}: dict[str, tuple]` — p10/p90 cache, cleared alongside bounds cache

---

## Running the App

```bash
cd /home/claude/my-vault/london_school_stats
source venv_app/bin/activate
streamlit run app.py
```

Note: `venv/` and `venv2/` are broken. Use `venv_app/` only.
