"""
Step 4: Show filtered school shortlist with neighbourhood data.
"""

import streamlit as st
from utils.db import query_schools, la_name_to_code
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
                    st.caption(f"Inspected {school['OFSTEDLASTINSP'][:7]}")
            else:
                st.caption("No Ofsted data")

        # Score + key metric
        col1, col2, col3 = st.columns(3)
        with col1:
            if score is not None:
                st.metric("Composite score", f"{score:.0f}/100")
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

        # Score bar
        if score is not None:
            st.caption(f"Score: {_score_bar(score)} {score:.0f}")

        # Neighbourhood row
        st.markdown("**Neighbourhood**")
        nb_col1, nb_col2, nb_col3 = st.columns(3)

        with nb_col1:
            if house_price:
                st.metric(
                    "Avg house price",
                    f"£{house_price:,.0f}",
                    help="Approximate 2024 median for this borough (Land Registry).",
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
                    help=f"Total crimes within ~1 mile radius, {month} (data.police.uk).",
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
            st.session_state.step = 5
            st.rerun()


def render():
    st.header("Step 4 of 5 — Your shortlist")

    criteria = st.session_state.get("criteria", {})
    selected_las = st.session_state.get("selected_las", [])
    ks_keys = st.session_state.get("ks_keys", ["ks4"])

    la_names = [la["la_name"] for la in selected_las]
    la_codes = la_name_to_code(la_names)

    if not la_codes:
        st.error("No boroughs selected. Please go back.")
        if st.button("← Back"):
            st.session_state.step = 3
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
                min_score=criteria.get("min_score", 40),
                include_no_ofsted=criteria.get("include_no_ofsted", True),
            )
            all_results[ks_key] = rows
        st.session_state.shortlist_results = all_results
        st.session_state._shortlist_key = cache_key
        # Clear neighbourhood cache when schools change
        st.session_state.pop("neighbourhood_data", None)

    all_results = st.session_state.shortlist_results
    total = sum(len(v) for v in all_results.values())

    if total == 0:
        st.warning(
            "No schools matched your criteria. Try loosening the filters — "
            "lower the score floor, add more school types, or widen Ofsted selection."
        )
        col_back, col_tweak = st.columns([1, 1])
        with col_back:
            if st.button("← Back to criteria"):
                st.session_state.step = 3
                st.rerun()
        return

    st.caption(f"Found **{total} school{'s' if total != 1 else ''}** matching your criteria.")

    # Sort control
    sort_options = ["Composite score (best first)", "Borough (A–Z)", "School name (A–Z)"]
    sort_by = st.selectbox("Sort by", sort_options, index=0)

    # Fetch neighbourhood data for all schools (cached)
    all_schools_flat = [s for schools in all_results.values() for s in schools]
    if "neighbourhood_data" not in st.session_state:
        st.session_state.neighbourhood_data = _fetch_neighbourhood(all_schools_flat[:20])

    nb_data = st.session_state.neighbourhood_data

    # Sort
    for ks_key, schools in all_results.items():
        if sort_by == "Borough (A–Z)":
            schools.sort(key=lambda s: (s.get("LANAME", ""), -(s.get("composite_score") or 0)))
        elif sort_by == "School name (A–Z)":
            schools.sort(key=lambda s: s.get("SCHNAME", ""))
        # Default: already sorted by composite_score DESC from query

    # Display by phase
    for ks_key in ks_keys:
        schools = all_results.get(ks_key, [])
        if not schools:
            continue

        st.subheader(f"{_KS_LABELS[ks_key]} ({len(schools)} schools)")

        for i, school in enumerate(schools[:20]):
            urn = school["URN"]
            nb = nb_data.get(urn, {})
            _school_card(school, nb, ks_key, i)

        if len(schools) > 20:
            st.caption(f"Showing top 20 of {len(schools)}. Tighten your filters to see fewer.")

    st.divider()
    col_back, _ = st.columns([1, 3])
    with col_back:
        if st.button("← Back to criteria"):
            st.session_state.step = 3
            st.rerun()
