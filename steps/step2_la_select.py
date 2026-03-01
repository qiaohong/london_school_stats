"""
Step 2: Resolve work postcode, estimate commute to each LA, recommend top 3,
and let the user confirm/adjust their borough selection.

Ranking heuristic: 50% commute score + 50% school quality score.
  - Commute score: 1 - (mid_commute / max_feasible_commute), normalised across all passing LAs.
  - School quality: avg composite score across relevant phases, from metrics_la.
"""

import sqlite3
import os
import streamlit as st
from utils.commute import resolve_postcode, filter_las_by_commute, load_profiles, estimate_commute
from utils.age_stage import phases_to_ks_keys

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "schools.db")

_PHASE_MAP = {"ks2": "KS2", "ks4": "KS4", "ks5": "KS5"}


def _all_phases_for_children() -> list[str]:
    seen = set()
    result = []
    for child in st.session_state.get("children", []):
        for p in child.get("phases", []):
            k = p["phase"]
            if k not in seen and k != "Nursery":
                seen.add(k)
                result.append(k)
    return result


def _ks_keys_for_children() -> list[str]:
    keys = []
    for child in st.session_state.get("children", []):
        for k in phases_to_ks_keys(child.get("phases", [])):
            if k not in keys:
                keys.append(k)
    return keys


def _la_school_quality(ks_keys: list[str]) -> dict[str, float]:
    """
    Return {la_name: avg_composite} averaged across the relevant phases.
    Scores come from metrics_la.avg_composite (0–100).
    """
    if not ks_keys:
        return {}
    phases = [_PHASE_MAP[k] for k in ks_keys if k in _PHASE_MAP]
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()
    placeholders = ",".join("?" * len(phases))
    cur.execute(
        f"SELECT borough, AVG(avg_composite) FROM metrics_la WHERE phase IN ({placeholders}) GROUP BY borough",
        phases,
    )
    result = {row[0]: row[1] for row in cur.fetchall() if row[1] is not None}
    conn.close()
    return result


_HIGH_SCORE_THRESHOLD = 60  # above-median with clear buffer; >=70 leaves some LAs with zero


def _la_high_score_count(ks_keys: list[str]) -> dict[str, int]:
    """
    Return {la_name: count} of distinct schools with composite_score >= 60,
    summed across the relevant phase tables.
    """
    if not ks_keys:
        return {}
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()
    counts: dict[str, int] = {}
    for ks_key in ks_keys:
        table = f"metrics_{ks_key}"
        cur.execute(
            f"SELECT LANAME, COUNT(DISTINCT URN) FROM {table} "
            f"WHERE composite_score >= ? GROUP BY LANAME",
            (_HIGH_SCORE_THRESHOLD,),
        )
        for row in cur.fetchall():
            counts[row[0]] = counts.get(row[0], 0) + row[1]
    conn.close()
    return counts


def _rank_las(
    results: list[dict],
    quality: dict[str, float],
    high_count: dict[str, int],
) -> list[dict]:
    """
    Re-rank LAs that pass commute filter by combined score:
      35% commute + 30% avg school quality + 35% count of schools scoring ≥ 70.
    """
    if not results:
        return results

    mids = [(la["commute_min"] + la["commute_max"]) / 2 for la in results]
    max_mid = max(mids) or 1
    min_mid = min(mids) or 0

    max_quality = max(quality.values()) if quality else 100
    min_quality = min(quality.values()) if quality else 0
    quality_range = max_quality - min_quality or 1

    max_count = max(high_count.values()) if high_count else 1
    min_count = min(high_count.values()) if high_count else 0
    count_range = max_count - min_count or 1

    scored = []
    for la, mid in zip(results, mids):
        commute_score = 1 - (mid - min_mid) / (max_mid - min_mid + 1)
        q = quality.get(la["la_name"], 50)
        quality_score = (q - min_quality) / quality_range
        c = high_count.get(la["la_name"], 0)
        count_score = (c - min_count) / count_range
        combined = 0.35 * commute_score + 0.30 * quality_score + 0.35 * count_score
        scored.append({**la, "_combined": combined, "_quality": q, "_high_score_count": c})

    scored.sort(key=lambda x: -x["_combined"])
    return scored


def render():
    st.header("Step 2 of 5 — Choose your areas")

    postcode = st.session_state.get("work_postcode", "")
    limit = st.session_state.get("commute_limit", 40)
    flex = st.session_state.get("flex_minutes", 0)
    ks_keys = _ks_keys_for_children()

    effective = limit + flex
    st.caption(
        f"Finding London boroughs reachable within **{limit} min**"
        + (f" (+ {flex} min, {int(flex/(limit or 1)*100)}% buffer)" if flex else "")
        + f" from **{postcode}** by public transport."
    )

    # Resolve postcode → lat/lng (cached in session)
    if "work_latlng" not in st.session_state or st.session_state.get("_postcode_cached") != postcode:
        with st.spinner("Resolving postcode…"):
            coords = resolve_postcode(postcode)
        if coords is None:
            st.error(f"Could not resolve postcode **{postcode}**. Please go back and check it.")
            if st.button("← Back"):
                st.session_state.step = 1
                st.rerun()
            return
        st.session_state.work_latlng = coords
        st.session_state._postcode_cached = postcode

    work_lat, work_lng = st.session_state.work_latlng

    # Compute commute estimates + quality ranking (cached)
    cache_key = (postcode, limit, flex, tuple(ks_keys))
    if "la_commute_results" not in st.session_state or st.session_state.get("_commute_key") != cache_key:
        with st.spinner("Estimating commute times and school quality by borough…"):
            results = filter_las_by_commute(work_lat, work_lng, limit, flex)
            quality = _la_school_quality(ks_keys)
            high_count = _la_high_score_count(ks_keys)
            ranked = _rank_las(results, quality, high_count)
        st.session_state.la_commute_results = ranked
        st.session_state._commute_key = cache_key

    results = st.session_state.la_commute_results
    all_profiles = load_profiles()
    quality = _la_school_quality(ks_keys)

    recommended = results[:3]
    recommended_codes = {la["la_code"] for la in recommended}

    phases_label = " + ".join(_all_phases_for_children()) or "schools"

    if recommended:
        st.subheader(f"Recommended boroughs for {phases_label}")
        st.caption(
            "Ranked by commute time (35%), average school quality (30%), "
            "and number of schools scoring ≥ 60/100 (35%)."
        )
        for la in recommended:
            mn, mx = la["commute_min"], la["commute_max"]
            lines = ", ".join(la["lines"][:3])
            q = quality.get(la["la_name"])
            q_str = f" · Quality: **{q:.0f}/100**" if q else ""
            hc = la.get("_high_score_count", 0)
            with st.expander(f"**{la['la_name']}** — {mn}–{mx} min commute", expanded=True):
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(la["character"])
                    st.caption(f"Transport: {lines} · Zones {la['zone_min']}–{la['zone_max']}{q_str}")
                with cols[1]:
                    st.metric("Commute", f"{mn}–{mx} min")
                    if q:
                        st.metric("Avg quality", f"{q:.0f}/100",
                                  help="Average composite score across relevant phases (London avg = 50).")
                    st.metric("Schools ≥ 60", str(hc),
                              help="Number of schools with composite score ≥ 60/100 across relevant phases (above London median with a clear margin).")
    else:
        st.warning(
            f"No boroughs found within {effective} minutes of {postcode}. "
            "Try increasing your commute limit or using the flexible option."
        )

    st.divider()
    st.subheader("Confirm your borough selection")
    st.caption("Select the boroughs you want to search schools in. You can include others beyond the recommended ones.")

    prev_selected = st.session_state.get("selected_la_codes", list(recommended_codes))

    other_profiles = [p for p in all_profiles if p["la_code"] not in recommended_codes]
    other_profiles.sort(key=lambda x: x["la_name"])
    all_ordered = recommended + other_profiles

    selected_codes = []
    col1, col2 = st.columns(2)
    for i, la in enumerate(all_ordered):
        col = col1 if i % 2 == 0 else col2
        is_recommended = la["la_code"] in recommended_codes
        mn = la.get("commute_min")
        mx = la.get("commute_max")
        if mn is None:
            mn, mx = estimate_commute(la, work_lat, work_lng)

        label = f"⭐ {la['la_name']}" if is_recommended else la["la_name"]
        checked = col.checkbox(
            f"{label}  ({mn}–{mx} min)",
            value=la["la_code"] in prev_selected,
            key=f"la_check_{la['la_code']}",
        )
        if checked:
            selected_codes.append(la["la_code"])

    st.divider()
    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
    with col_next:
        if st.button(
            "Next: Set school criteria →",
            type="primary",
            disabled=len(selected_codes) == 0,
        ):
            selected_las = [la for la in all_profiles if la["la_code"] in selected_codes]
            st.session_state.selected_la_codes = selected_codes
            st.session_state.selected_las = selected_las
            st.session_state.ks_keys = ks_keys
            st.session_state.step = 3
            st.rerun()

    if not selected_codes:
        st.warning("Select at least one borough to continue.")
