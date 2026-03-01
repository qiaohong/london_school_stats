"""
Step 5: Full school detail view — metrics, borough comparison, admissions info, Rightmove link.
"""

import json
import os
import sqlite3
import streamlit as st
from utils.rightmove import build_url, describe_radius
from utils.neighbourhood import crime_label, CRIME_CATEGORY_LABELS

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "schools.db")
_ADMISSIONS_URLS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "la_admissions_urls.json")

with open(_ADMISSIONS_URLS_PATH) as f:
    _ADMISSIONS_URLS = json.load(f)

_OFSTED_COLOUR = {
    "Outstanding":        "🟢",
    "Good":               "🔵",
    "Requires improvement": "🟡",
    "Inadequate":         "🔴",
}


def _la_avg(borough: str, phase: str) -> dict:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM metrics_la WHERE borough=? AND phase=?",
        (borough, phase.upper()),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


def _london_avg(ks_key: str) -> dict:
    """Compute London-wide averages from the metrics table."""
    table = f"metrics_{ks_key}"
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if ks_key == "ks2":
        cur.execute(
            f"SELECT AVG(composite_score) as composite, AVG(avg_progress) as progress, "
            f"AVG(pct_rwm_expected) as rwm, AVG(absence_pct) as absence FROM {table}"
        )
    elif ks_key == "ks4":
        cur.execute(
            f"SELECT AVG(composite_score) as composite, AVG(progress8) as progress, "
            f"AVG(pct_grade5_eng_maths) as basics5, AVG(absence_pct) as absence FROM {table}"
        )
    else:
        cur.execute(
            f"SELECT AVG(composite_score) as composite, AVG(alevel_value_added) as progress, "
            f"AVG(pct_aab_facilitating) as aab, AVG(absence_pct) as absence FROM {table}"
        )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


def _delta(school_val, avg_val, higher_is_better=True, fmt=".1f") -> tuple[str, str]:
    """Return (delta_str, delta_colour) for st.metric."""
    if school_val is None or avg_val is None:
        return None, None
    diff = school_val - avg_val
    label = f"{diff:+{fmt}} vs London avg"
    colour = "normal" if (diff >= 0) == higher_is_better else "inverse"
    return label, colour


def _section_metrics_ks2(school: dict, la_avg: dict, lon_avg: dict):
    st.subheader("Primary performance (KS2)")
    cols = st.columns(4)
    metrics = [
        ("Composite score",  school.get("composite_score"),    lon_avg.get("composite"),  True,  ".0f"),
        ("Avg progress",     school.get("avg_progress"),       None,                       True,  "+.2f"),
        ("RWM expected %",   school.get("pct_rwm_expected"),   None,                       True,  ".1f"),
        ("Absence %",        school.get("absence_pct"),        lon_avg.get("absence"),     False, ".1f"),
    ]
    for col, (label, val, avg, hib, fmt) in zip(cols, metrics):
        if val is not None:
            delta_str, _ = _delta(val, avg, hib, fmt) if avg else (None, None)
            col.metric(label, f"{val:{fmt}}", delta=delta_str)
        else:
            col.metric(label, "n/a")

    # Borough comparison
    if la_avg:
        with st.expander("Borough comparison"):
            b_cols = st.columns(3)
            b_cols[0].metric("Borough composite avg", f"{la_avg.get('avg_composite', 0):.0f}")
            b_cols[1].metric("Borough progress avg",  f"{la_avg.get('avg_progress', 0):+.2f}" if la_avg.get('avg_progress') else "n/a")
            b_cols[2].metric("Borough absence avg",   f"{la_avg.get('avg_absence_pct', 0):.1f}%")


def _section_metrics_ks4(school: dict, la_avg: dict, lon_avg: dict):
    st.subheader("Secondary performance (KS4)")
    cols = st.columns(4)
    metrics = [
        ("Composite score",   school.get("composite_score"),       lon_avg.get("composite"), True,  ".0f"),
        ("Progress 8",        school.get("progress8"),             None,                      True,  "+.2f"),
        ("Grade 5+ E&M",      school.get("pct_grade5_eng_maths"),  None,                      True,  ".1f"),
        ("Absence %",         school.get("absence_pct"),           lon_avg.get("absence"),    False, ".1f"),
    ]
    for col, (label, val, avg, hib, fmt) in zip(cols, metrics):
        if val is not None:
            delta_str, _ = _delta(val, avg, hib, fmt) if avg else (None, None)
            col.metric(label, f"{val:{fmt}}", delta=delta_str)
        else:
            col.metric(label, "n/a")

    # More detail
    with st.expander("More metrics"):
        mc = st.columns(3)
        mc[0].metric("Attainment 8",   f"{school.get('attainment8', 0):.1f}"   if school.get('attainment8') else "n/a")
        mc[1].metric("EBacc 4+",       f"{school.get('pct_ebacc_4plus', 0):.1f}%" if school.get('pct_ebacc_4plus') else "n/a")
        mc[2].metric("Destinations (education)", f"{school.get('dest_pct_education', 0):.1f}%" if school.get('dest_pct_education') else "n/a")
        mc2 = st.columns(3)
        mc2[0].metric("FSM gap (P8)",  f"{school.get('fsm_gap_progress8', 0):+.2f}" if school.get('fsm_gap_progress8') else "n/a",
                       help="Progress 8 gap between FSM and non-FSM pupils. Closer to 0 = more equitable.")
        mc2[1].metric("NEET %",        f"{school.get('dest_pct_neet', 0):.1f}%" if school.get('dest_pct_neet') else "n/a")
        mc2[2].metric("Cohort size",   f"{int(school.get('ks4_cohort', 0))}" if school.get('ks4_cohort') else "n/a")

    if la_avg:
        with st.expander("Borough comparison"):
            b_cols = st.columns(3)
            b_cols[0].metric("Borough composite avg", f"{la_avg.get('avg_composite', 0):.0f}")
            b_cols[1].metric("Borough Progress 8 avg", f"{la_avg.get('avg_progress8', 0):+.2f}" if la_avg.get('avg_progress8') is not None else "n/a")
            b_cols[2].metric("Borough absence avg",  f"{la_avg.get('avg_absence_pct', 0):.1f}%")


def _section_metrics_ks5(school: dict, la_avg: dict, lon_avg: dict):
    st.subheader("Sixth form performance (KS5)")
    cols = st.columns(4)
    metrics = [
        ("Composite score",  school.get("composite_score"),      lon_avg.get("composite"), True,  ".0f"),
        ("A-level VA",       school.get("alevel_value_added"),   None,                      True,  "+.2f"),
        ("AAB facilitating", school.get("pct_aab_facilitating"), None,                      True,  ".1f"),
        ("Absence %",        school.get("absence_pct"),          lon_avg.get("absence"),    False, ".1f"),
    ]
    for col, (label, val, avg, hib, fmt) in zip(cols, metrics):
        if val is not None:
            delta_str, _ = _delta(val, avg, hib, fmt) if avg else (None, None)
            col.metric(label, f"{val:{fmt}}", delta=delta_str)
        else:
            col.metric(label, "n/a")

    with st.expander("More metrics"):
        mc = st.columns(2)
        mc[0].metric("HE destinations", f"{school.get('dest_pct_he', 0):.1f}%" if school.get('dest_pct_he') else "n/a")
        mc[1].metric("A-level cohort",  f"{int(school.get('alevel_cohort', 0))}" if school.get('alevel_cohort') else "n/a")


def render():
    school = st.session_state.get("selected_school")
    nb = st.session_state.get("selected_school_nb", {})
    ks_key = st.session_state.get("selected_ks_key", "ks4")

    if not school:
        st.warning("No school selected. Please go back to the shortlist.")
        if st.button("← Back to shortlist"):
            st.session_state.step = 4
            st.rerun()
        return

    # ── Header ────────────────────────────────────────────────────────────────
    ofsted = school.get("OFSTEDRATING")
    ofsted_sym = _OFSTED_COLOUR.get(ofsted, "⚪")
    la_name = school.get("LANAME", "")
    phase_map = {"ks2": "KS2", "ks4": "KS4", "ks5": "KS5"}

    st.header(school["SCHNAME"])
    col_info, col_ofsted = st.columns([3, 1])
    with col_info:
        st.caption(
            f"{la_name} · {school.get('MINORGROUP', '')} · "
            f"{school.get('GENDER', '')} · {school.get('ADMPOL') or 'Non-selective'}"
        )
        if school.get("RELCHAR") and school["RELCHAR"] not in ("Does not apply", None, ""):
            st.caption(f"Religious character: {school['RELCHAR']}")
        st.caption(f"Postcode: {school.get('POSTCODE', 'n/a')}")
    with col_ofsted:
        if ofsted:
            st.markdown(f"### {ofsted_sym}")
            st.markdown(f"**{ofsted}**")
            if school.get("OFSTEDLASTINSP"):
                st.caption(f"Inspected {school['OFSTEDLASTINSP'][:7]}")

    st.divider()

    # ── Performance metrics ───────────────────────────────────────────────────
    borough = la_name
    la_avg = _la_avg(borough, phase_map[ks_key])
    lon_avg = _london_avg(ks_key)

    if ks_key == "ks2":
        _section_metrics_ks2(school, la_avg, lon_avg)
    elif ks_key == "ks4":
        _section_metrics_ks4(school, la_avg, lon_avg)
    else:
        _section_metrics_ks5(school, la_avg, lon_avg)

    st.divider()

    # ── Neighbourhood summary ─────────────────────────────────────────────────
    st.subheader("Neighbourhood")
    nb_c1, nb_c2 = st.columns(2)

    crime_data = nb.get("crime", {})
    with nb_c1:
        if crime_data and crime_data.get("total", 0) > 0:
            label, colour = crime_label(crime_data["total"])
            month = crime_data.get("month", "")
            st.metric("Crime (1-mile radius)", f"{crime_data['total']:,} / month",
                      help=f"All crimes within ~1 mile, {month} (data.police.uk)")
            st.caption(f"Level: :{colour}[{label}]")

            by_cat = crime_data.get("by_category", {})
            if by_cat:
                top = sorted(by_cat.items(), key=lambda x: -x[1])[:6]
                rows = [f"| {CRIME_CATEGORY_LABELS.get(k, k)} | {v} |" for k, v in top]
                st.markdown("| Category | Count |\n|---|---|\n" + "\n".join(rows))
        else:
            st.caption("Crime data not available for this location.")

    with nb_c2:
        from utils.neighbourhood import house_price_for_la
        price = house_price_for_la(la_name)
        if price:
            st.metric("Avg house price", f"£{price:,.0f}",
                      help="Approximate 2024 borough median (Land Registry).")
        st.caption(
            "💡 Use the Rightmove search below to see current listings "
            "near this school."
        )

    st.divider()

    # ── Admissions info ───────────────────────────────────────────────────────
    st.subheader("Admissions")

    admpol = school.get("ADMPOL") or "Non-selective"
    relchar = school.get("RELCHAR")
    la_url = _ADMISSIONS_URLS.get(la_name)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Admissions policy:** {admpol}")
        if relchar and relchar not in ("Does not apply", None, ""):
            st.markdown(f"**Religious character:** {relchar}")
            st.caption("Faith schools may prioritise applicants of that faith.")
        if admpol == "Selective":
            st.warning("This school requires an entrance exam (selective admissions).")

    with col_b:
        st.markdown("**Admission cut-off distance**")
        st.info(
            "We don't yet have cut-off distance data for this school. "
            "Check the borough admissions page for historical allocation distances.",
            icon="ℹ️",
        )
        if la_url:
            st.link_button(
                f"View {la_name} admissions data →",
                url=la_url,
            )

    st.caption(
        "Most London boroughs measure distance **straight-line (as the crow flies)** "
        "from home to school gate. Cut-off distances typically stretch further "
        "after National Offer Day as families decline places."
    )

    st.divider()

    # ── Rightmove search ──────────────────────────────────────────────────────
    st.subheader("Search for properties near this school")

    postcode = school.get("POSTCODE", "")
    outcode = postcode.split()[0] if postcode else ""

    # Optional filters
    with st.expander("Filter your property search (optional)"):
        rm_col1, rm_col2, rm_col3 = st.columns(3)
        with rm_col1:
            listing_type = st.radio("Listing type", ["sale", "rent"],
                                    format_func=lambda x: "For sale" if x == "sale" else "To rent")
        with rm_col2:
            max_price = st.number_input("Max price (£)", min_value=0, max_value=5_000_000,
                                        value=0, step=50_000)
            max_price = int(max_price) if max_price > 0 else None
        with rm_col3:
            min_beds = st.number_input("Min bedrooms", min_value=0, max_value=6, value=0, step=1)
            min_beds = int(min_beds) if min_beds > 0 else None

    rm_url = build_url(
        postcode=postcode,
        cutoff_km=None,   # no cutoff data yet
        max_price=max_price,
        min_bedrooms=min_beds,
        listing_type=listing_type,
    )
    radius_desc = describe_radius(None)

    st.markdown(f"Searching within **{radius_desc}** of **{outcode}**.")
    st.link_button(
        "Search properties on Rightmove →",
        url=rm_url,
        type="primary",
    )
    st.caption(
        "Opens Rightmove in a new tab. Adjust the radius on Rightmove once there. "
        "When admission cut-off data becomes available, the radius will be set automatically."
    )

    st.divider()

    # ── Navigation ────────────────────────────────────────────────────────────
    col_back, col_restart = st.columns([1, 1])
    with col_back:
        if st.button("← Back to shortlist"):
            st.session_state.step = 4
            st.rerun()
    with col_restart:
        if st.button("Start over"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
