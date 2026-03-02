"""
Step 5: Show filtered school shortlist with neighbourhood data.
"""

import streamlit as st
from utils.db import query_schools, la_name_to_code
from utils.score_config import attributes_for_ks, fetch_london_bounds, fetch_top10_thresholds, get_available_attributes
from utils.neighbourhood import (
    batch_geocode,
    get_latest_crime_month,
    get_crime_data,
    crime_label,
    house_price_for_la,
    CRIME_CATEGORY_LABELS,
    PRIORITY_CATEGORIES,
)

_KS_LABELS = {"ks2": "Primary", "ks4": "Secondary", "ks5": "Sixth Form"}

# Standard entry point: {ks_key: (child_year_group, applying_for, deadline_note)}
_STANDARD_ENTRY = {
    "ks2": (( -1,  0), "Reception",        "deadline ~15 Jan for Sept start"),
    "ks4": ((  6,  6), "Year 7",            "deadline ~31 Oct for Sept start"),
    "ks5": (( 11, 11), "Year 12",           "deadline varies by school"),
}


def _phase_admission_type(ks_key: str) -> tuple[str, str]:
    """
    Return (type_label, detail) for the admission process relevant to this phase,
    based on the children stored in session state.
    """
    children = st.session_state.get("children", [])
    entry = _STANDARD_ENTRY.get(ks_key)
    if entry:
        yg_range, applying_for, deadline = entry
        yg_min, yg_max = yg_range
        for child in children:
            yg = child.get("year_group")
            if yg is not None and yg_min <= yg <= yg_max:
                return "Standard admission", f"applying for {applying_for} ({deadline})"
    return "In-year admission", "joining mid-phase — apply directly to school or LA"

_MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def _fmt_insp_date(raw: str) -> str:
    """Convert 'DD-MM-YYYY' → 'Mon YYYY'. Returns raw string on parse failure."""
    try:
        parts = raw.split("-")
        if len(parts) == 3:
            month = _MONTH_ABBR[int(parts[1]) - 1]
            return f"{month} {parts[2]}"
    except Exception:
        pass
    return raw

_OFSTED_EMOJI = {
    "Outstanding": "★",
    "Good": "✓",
    "Requires improvement": "⚠",
    "Inadequate": "✗",
    None: "–",
}


def _score_bar(score: float | None, width: int = 12) -> str:
    if score is None:
        return "n/a"
    filled = round((score / 100) * width)
    return "█" * filled + "░" * (width - filled)


def _fetch_neighbourhood(schools: list[dict]) -> dict:
    """
    Geocode all school postcodes and fetch crime data for each.
    Returns {URN: {lat, lng, crime}} dict.
    """
    postcodes = [s["POSTCODE"] for s in schools if s.get("POSTCODE")]
    geo = batch_geocode(postcodes)
    latest_month = get_latest_crime_month()

    result = {}
    progress = st.progress(0, text="Loading neighbourhood data…")
    for i, school in enumerate(schools):
        pc = (school.get("POSTCODE") or "").strip().upper()
        coords = geo.get(pc)
        crime = None
        if coords:
            crime = get_crime_data(coords[0], coords[1], latest_month)
        result[school["URN"]] = {
            "lat": coords[0] if coords else None,
            "lng": coords[1] if coords else None,
            "crime": crime,
        }
        progress.progress((i + 1) / len(schools), text=f"Loading neighbourhood data… ({i+1}/{len(schools)})")
    progress.empty()
    return result


def _school_card(school: dict, nb: dict, ks_key: str, idx: int):
    urn = school["URN"]
    ofsted = school.get("OFSTEDRATING")
    ofsted_sym = _OFSTED_EMOJI.get(ofsted, "–")
    score = school.get("composite_score")
    la_name = school.get("LANAME", "")
    house_price = house_price_for_la(la_name)

    with st.container(border=True):
        # Header row
        col_name, col_badge = st.columns([4, 1])
        with col_name:
            st.markdown(f"### {school['SCHNAME']}")
            st.caption(
                f"{la_name} · {school.get('MINORGROUP', '')} · "
                f"{school.get('GENDER', '')} · {school.get('ADMPOL') or 'Non-selective'}"
            )
        with col_badge:
            if ofsted:
                colour = {"Outstanding": "🟢", "Good": "🔵", "Requires improvement": "🟡", "Inadequate": "🔴"}.get(ofsted, "⚪")
                st.markdown(f"**{colour} {ofsted}**")
                if school.get("OFSTEDLASTINSP"):
                    st.caption(f"Inspected {_fmt_insp_date(school['OFSTEDLASTINSP'])}")
            else:
                st.caption("No Ofsted data")

        # Score + key metrics
        custom_score = school.get("custom_score")
        weights = st.session_state.get("score_weights", {})
        valid_keys = attributes_for_ks(ks_key)
        applicable = {k: v for k, v in weights.items() if k in valid_keys}
        top_attrs = sorted(applicable.items(), key=lambda x: -x[1])[:2]
        attr_label = {fk: lbl for fk, lbl, _, _ in get_available_attributes([ks_key])}

        def _fmt_val(v, field_key):
            if v is None:
                return "n/a"
            if isinstance(v, float) and abs(v) < 5:
                return f"{v:+.2f}"
            if isinstance(v, float):
                return f"{v:.1f}"
            return str(v)

        col1, col2, col3 = st.columns(3)
        with col1:
            if custom_score is not None:
                sys_note = f" (sys: {score:.0f})" if score is not None else ""
                st.metric("Your score", f"{custom_score:.0f}/100", help=f"Custom score from your Step 2 weights.{sys_note}")
            elif score is not None:
                st.metric("Composite score", f"{score:.0f}/100")

        if top_attrs:
            for col, (field_key, _) in zip([col2, col3], top_attrs):
                with col:
                    st.metric(
                        attr_label.get(field_key, field_key),
                        _fmt_val(school.get(field_key), field_key),
                    )
        else:
            with col2:
                if ks_key == "ks2":
                    v = school.get("avg_progress")
                    st.metric("Avg progress", f"{v:+.1f}" if v is not None else "n/a")
                elif ks_key == "ks4":
                    v = school.get("progress8")
                    st.metric("Progress 8", f"{v:+.2f}" if v is not None else "n/a")
                elif ks_key == "ks5":
                    v = school.get("alevel_value_added")
                    st.metric("A-level VA", f"{v:+.2f}" if v is not None else "n/a")
            with col3:
                abs_pct = school.get("absence_pct")
                st.metric("Absence", f"{abs_pct:.1f}%" if abs_pct is not None else "n/a")

        # Neighbourhood row
        st.markdown("**Neighbourhood**")
        nb_col1, nb_col2, nb_col3 = st.columns(3)

        with nb_col1:
            if house_price:
                st.metric(
                    "Avg house price",
                    f"£{house_price:,.0f}",
                )
                st.caption(
                    "2024 borough median (Land Registry). "
                    "All schools in the same borough show the same figure — "
                    "intra-borough variation can be large."
                )
            else:
                st.caption("House price: n/a")

        with nb_col2:
            crime_data = nb.get("crime")
            if crime_data and crime_data["total"] > 0:
                label, colour = crime_label(crime_data["total"])
                month = crime_data.get("month", "")
                st.metric(
                    "Crime nearby",
                    f"{crime_data['total']:,} / month",
                )
                st.caption(
                    f"All crimes within ~1 mile of the **school's postcode** "
                    f"({month}, data.police.uk)."
                )
                st.caption(f"Level: :{colour}[{label}]")
            elif crime_data is not None:
                st.caption("Crime data unavailable")
            else:
                st.caption("Crime: not loaded")

        with nb_col3:
            if crime_data and crime_data["by_category"]:
                top_cats = sorted(
                    [(k, v) for k, v in crime_data["by_category"].items() if k in PRIORITY_CATEGORIES],
                    key=lambda x: -x[1],
                )[:3]
                if top_cats:
                    lines = [f"{CRIME_CATEGORY_LABELS.get(k, k)}: {v}" for k, v in top_cats]
                    st.caption("Key crime types:\n" + "\n".join(lines))

        # Action button
        if st.button("View full details →", key=f"detail_{urn}_{idx}", type="primary"):
            st.session_state.selected_school = school
            st.session_state.selected_school_nb = nb
            st.session_state.selected_ks_key = ks_key
            st.session_state.step = 6
            st.rerun()


def _apply_custom_score(schools: list[dict], ks_key: str) -> None:
    """
    Compute a custom_score for each school (in-place) from session state score_weights.
    Normalises against London-wide min/max (all schools in metrics_{ks_key}), so scores
    are deterministic and do not change with shortlist composition.
    Missing values are imputed at 0.5 (midpoint) for numeric mode, or 0 for binary mode.
    """
    weights: dict[str, int] = st.session_state.get("score_weights", {})
    directions: dict[str, bool | None] = st.session_state.get("score_weight_directions", {})
    binary_flags: dict[str, bool] = st.session_state.get("score_weight_binary", {})
    if not weights or not schools:
        return

    # Only use attributes valid for this ks_key
    valid_keys = attributes_for_ks(ks_key)
    applicable = {k: v for k, v in weights.items() if k in valid_keys}
    if not applicable:
        return

    total_weight = sum(applicable.values())
    if total_weight == 0:
        return

    # Fetch London-wide bounds for ALL fields in this ks_key
    bounds_key = f"_london_bounds_{ks_key}"
    if bounds_key not in st.session_state:
        st.session_state[bounds_key] = fetch_london_bounds(ks_key, list(attributes_for_ks(ks_key)))
    bounds = st.session_state[bounds_key]

    # Fetch top-10% thresholds for binary mode attributes
    top10_key = f"_london_top10_{ks_key}"
    if top10_key not in st.session_state:
        st.session_state[top10_key] = fetch_top10_thresholds(ks_key, list(attributes_for_ks(ks_key)))
    top10 = st.session_state[top10_key]

    for school in schools:
        score_sum = 0.0
        for key, weight in applicable.items():
            val = school.get(key)
            if binary_flags.get(key):
                p10, p90 = top10.get(key, (None, None))
                hib = directions.get(key, True)
                if val is None:
                    norm = 0.0
                elif hib:
                    norm = 1.0 if (p90 is not None and val >= p90) else 0.0
                else:
                    norm = 1.0 if (p10 is not None and val <= p10) else 0.0
            else:
                lo_hi = bounds.get(key)
                if lo_hi is None or val is None:
                    norm = 0.5
                else:
                    lo, hi = lo_hi
                    norm = 0.5 if hi == lo else (val - lo) / (hi - lo)
                if directions.get(key) is False:
                    norm = 1.0 - norm
            norm = max(0.0, min(1.0, norm))  # clamp to [0, 1]
            score_sum += norm * weight
        school["custom_score"] = round(score_sum / total_weight * 100, 1)


def render():
    st.header("Step 5 of 6 — Your shortlist")

    criteria = st.session_state.get("criteria", {})
    selected_las = st.session_state.get("selected_las", [])
    ks_keys = st.session_state.get("ks_keys", ["ks4"])

    la_names = [la["la_name"] for la in selected_las]
    la_codes = la_name_to_code(la_names)

    if not la_codes:
        st.error("No boroughs selected. Please go back.")
        if st.button("← Back"):
            st.session_state.step = 4
            st.rerun()
        return

    # Query schools (cached per session)
    cache_key = ("shortlist", tuple(sorted(la_codes)), tuple(sorted(ks_keys)), str(sorted(criteria.items())))
    if "shortlist_results" not in st.session_state or st.session_state.get("_shortlist_key") != cache_key:
        all_results = {}
        for ks_key in ks_keys:
            rows = query_schools(
                la_codes=la_codes,
                ks_key=ks_key,
                ofsted_ratings=criteria.get("ofsted_ratings", ["Outstanding", "Good"]),
                school_types=criteria.get("school_types", ["Academy", "Maintained school"]),
                admpol=criteria.get("admpol", "Any"),
                gender=criteria.get("gender", "Any"),
                faith_groups=criteria.get("faith_groups", []),
                include_no_ofsted=criteria.get("include_no_ofsted", True),
            )
            all_results[ks_key] = rows
        st.session_state.shortlist_results = all_results
        st.session_state._shortlist_key = cache_key
        # Clear neighbourhood cache when schools change
        st.session_state.pop("neighbourhood_data", None)
        # Clear London bounds and top-10% cache when weights may have changed
        for k in list(st.session_state.keys()):
            if k.startswith("_london_bounds_") or k.startswith("_london_top10_"):
                del st.session_state[k]

    all_results = st.session_state.shortlist_results

    # Apply custom scores if the user configured weights in step 2
    if st.session_state.get("score_weights"):
        for ks_key, schools in all_results.items():
            _apply_custom_score(schools, ks_key)

    total = sum(len(v) for v in all_results.values())

    if total == 0:
        st.warning(
            "No schools matched your criteria. Try loosening the filters — "
            "lower the score floor, add more school types, or widen Ofsted selection."
        )
        col_back, col_tweak = st.columns([1, 1])
        with col_back:
            if st.button("← Back to criteria"):
                st.session_state.step = 4
                st.rerun()
        return

    st.caption(f"Found **{total} school{'s' if total != 1 else ''}** matching your criteria.")

    # Custom score label
    using_custom = bool(st.session_state.get("score_weights"))
    score_label = "Your score" if using_custom else "Composite score"
    if using_custom:
        st.caption(
            f"Sorted by your **custom score** (built in Step 2). "
            "System composite score shown in brackets for reference."
        )

    # Sort control
    sort_options = [f"{score_label} (best first)", "Borough (A–Z)", "School name (A–Z)"]
    sort_by = st.selectbox("Sort by", sort_options, index=0)

    max_schools = criteria.get("max_schools", 20)

    # Fetch neighbourhood data for all schools (cached)
    all_schools_flat = [s for schools in all_results.values() for s in schools]
    if "neighbourhood_data" not in st.session_state:
        st.session_state.neighbourhood_data = _fetch_neighbourhood(all_schools_flat[:max_schools])

    nb_data = st.session_state.neighbourhood_data

    # Sort
    def _primary_score(s: dict) -> float:
        return s.get("custom_score") if using_custom and s.get("custom_score") is not None else (s.get("composite_score") or 0)

    for ks_key, schools in all_results.items():
        if sort_by == "Borough (A–Z)":
            schools.sort(key=lambda s: (s.get("LANAME", ""), -_primary_score(s)))
        elif sort_by == "School name (A–Z)":
            schools.sort(key=lambda s: s.get("SCHNAME", ""))
        else:
            schools.sort(key=lambda s: -_primary_score(s))

    # Display by phase
    for ks_key in ks_keys:
        schools = all_results.get(ks_key, [])
        if not schools:
            continue

        st.subheader(f"{_KS_LABELS[ks_key]} ({min(len(schools), max_schools)} of {len(schools)} schools)")

        for i, school in enumerate(schools[:max_schools]):
            urn = school["URN"]
            nb = nb_data.get(urn, {})
            _school_card(school, nb, ks_key, i)

        if len(schools) > max_schools:
            st.caption(f"Showing top {max_schools} of {len(schools)}. Increase the limit in Step 4 to see more.")

    st.divider()
    col_back, _ = st.columns([1, 3])
    with col_back:
        if st.button("← Back to criteria"):
            st.session_state.step = 4
            st.rerun()
