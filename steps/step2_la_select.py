"""
Step 2: Resolve work postcode, estimate commute to each LA, recommend top 3,
and let the user confirm/adjust their borough selection.
"""

import streamlit as st
from utils.commute import resolve_postcode, filter_las_by_commute, load_profiles
from utils.age_stage import phases_to_ks_keys


def _all_phases_for_children() -> list[str]:
    """Collect all unique school phase labels across all children."""
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
    """Collect DB keys (ks2/ks4/ks5) relevant across all children."""
    keys = []
    for child in st.session_state.get("children", []):
        for k in phases_to_ks_keys(child.get("phases", [])):
            if k not in keys:
                keys.append(k)
    return keys


def render():
    st.header("Step 2 of 5 — Choose your areas")

    postcode = st.session_state.get("work_postcode", "")
    limit = st.session_state.get("commute_limit", 40)
    flex = st.session_state.get("flex_minutes", 0)

    st.caption(
        f"Finding London boroughs reachable within **{limit} min**"
        + (f" (+ {flex} min flexible buffer)" if flex else "")
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

    # Compute commute estimates
    if "la_commute_results" not in st.session_state or st.session_state.get("_commute_key") != (postcode, limit, flex):
        with st.spinner("Estimating commute times to each borough…"):
            results = filter_las_by_commute(work_lat, work_lng, limit, flex)
        st.session_state.la_commute_results = results
        st.session_state._commute_key = (postcode, limit, flex)

    results = st.session_state.la_commute_results
    all_profiles = load_profiles()

    # Recommended (top 3 that fit)
    recommended = results[:3]
    recommended_codes = {la["la_code"] for la in recommended}

    phases_label = " + ".join(_all_phases_for_children()) or "schools"

    if recommended:
        st.subheader(f"Recommended boroughs for {phases_label}")
        st.caption("Based on commute time and transport connectivity.")
        for la in recommended:
            mn, mx = la["commute_min"], la["commute_max"]
            lines = ", ".join(la["lines"][:3])
            with st.expander(f"**{la['la_name']}** — {mn}–{mx} min commute", expanded=True):
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(la["character"])
                    st.caption(f"Transport: {lines} · Zones {la['zone_min']}–{la['zone_max']}")
                with cols[1]:
                    st.metric("Commute", f"{mn}–{mx} min")
    else:
        st.warning(
            f"No boroughs found within {limit + flex} minutes of {postcode}. "
            "Try increasing your commute limit or using the flexible option."
        )

    st.divider()
    st.subheader("Confirm your borough selection")
    st.caption("Select the boroughs you want to search schools in. You can include others beyond the recommended ones.")

    # Pre-select recommended boroughs
    prev_selected = st.session_state.get("selected_la_codes", list(recommended_codes))

    # Build options: recommended first, then rest alphabetically
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
            # Not in filtered results — compute on the fly
            from utils.commute import estimate_commute
            mn, mx = estimate_commute(la, work_lat, work_lng)

        label = la["la_name"]
        if is_recommended:
            label = f"⭐ {label}"
        sublabel = f"{mn}–{mx} min"
        checked = col.checkbox(
            f"{label}  ({sublabel})",
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
            st.session_state.ks_keys = _ks_keys_for_children()
            st.session_state.step = 3
            st.rerun()

    if not selected_codes:
        st.warning("Select at least one borough to continue.")
