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


def _school_details(urn: int) -> dict:
    """Fetch address and age range from the schools table by URN."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT STREET, LOCALITY, ADDRESS3, TOWN, POSTCODE, AGELOW, AGEHIGH "
        "FROM schools WHERE URN=? LIMIT 1",
        (urn,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


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
            delta_str, delta_colour = _delta(val, avg, hib, fmt) if avg else (None, "normal")
            col.metric(label, f"{val:{fmt}}", delta=delta_str, delta_color=delta_colour or "normal")
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
            delta_str, delta_colour = _delta(val, avg, hib, fmt) if avg else (None, "normal")
            col.metric(label, f"{val:{fmt}}", delta=delta_str, delta_color=delta_colour or "normal")
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
            delta_str, delta_colour = _delta(val, avg, hib, fmt) if avg else (None, "normal")
            col.metric(label, f"{val:{fmt}}", delta=delta_str, delta_color=delta_colour or "normal")
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
            total = crime_data["total"]
            month = crime_data.get("month", "")
            by_cat = crime_data.get("by_category", {})
            violent = by_cat.get("violent-crime", 0)
            violent_pct = round(violent / total * 100) if total else 0

            st.metric("Crime (1-mile radius)", f"{total:,} / month",
                      help=f"All recorded crimes within ~1 mile of the school's postcode, {month} (data.police.uk).")
            st.markdown(f"**Level: :{colour}[{label}]**")
            st.caption(
                f"Bands: Low < 400 · Moderate 400–699 · High 700–999 · Very high ≥ 1,000 "
                f"crimes/month in a 1-mile radius. "
                f"These reflect typical variation across London neighbourhoods."
            )
            if by_cat:
                top2 = sorted(by_cat.items(), key=lambda x: -x[1])[:2]
                top2_str = " and ".join(
                    f"{CRIME_CATEGORY_LABELS.get(k, k).lower()} ({v:,})"
                    for k, v in top2
                )
                st.caption(
                    f"The two most common crime types are {top2_str}. "
                    f"Violent crime accounts for **{violent:,} incidents ({violent_pct}%)** — "
                    f"the category most directly relevant to personal safety."
                )
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

    # ── School info ───────────────────────────────────────────────────────────
    st.subheader("School information")

    details = _school_details(school["URN"])

    info_col1, info_col2 = st.columns(2)
    with info_col1:
        # Full address
        addr_parts = [
            details.get("STREET"),
            details.get("LOCALITY"),
            details.get("ADDRESS3"),
            details.get("TOWN"),
            school.get("POSTCODE"),
        ]
        address = ", ".join(p for p in addr_parts if p)
        st.markdown(f"**Address**")
        st.write(address or school.get("POSTCODE", "n/a"))

        # Age range
        age_low = details.get("AGELOW")
        age_high = details.get("AGEHIGH")
        if age_low is not None and age_high is not None:
            st.markdown(f"**Age range:** {int(age_low)}–{int(age_high)}")

        # School type
        st.markdown(f"**Type:** {school.get('MINORGROUP', 'n/a')}")

    with info_col2:
        # Pupil numbers & context
        cohort = school.get("census_total_pupils") or school.get("ks4_cohort")
        if cohort:
            st.metric("Total pupils", f"{int(cohort):,}")

        fsm = school.get("pct_fsm")
        eal = school.get("pct_eal")
        sen = school.get("pct_sen_support")
        if fsm is not None:
            st.metric("Free school meals", f"{fsm:.1f}%",
                      help="% of pupils eligible for free school meals — a proxy for socioeconomic deprivation.")
        if eal is not None:
            st.metric("English as additional language", f"{eal:.1f}%",
                      help="% of pupils whose first language is not English (DfE census).")

    st.divider()

    # ── Admissions info ───────────────────────────────────────────────────────
    st.subheader("Admissions")

    admpol = school.get("ADMPOL") or "Non-selective"
    relchar = school.get("RELCHAR")
    la_url = _ADMISSIONS_URLS.get(la_name)

    # Standard vs in-year determination (including future phases)
    import datetime as _dt
    _today = _dt.date.today()
    _acad_start = _today.year if _today.month >= 9 else _today.year - 1

    # apply_yg: year group at which child makes the standard application
    # max_in_phase: max year group still within this phase (above = left phase)
    _ENTRY = {
        "ks2": {"apply_yg": -1, "max_in_phase":  6, "applying_for": "Reception",
                "deadline_fmt": lambda yr: f"~15 Jan {_acad_start + yr + 1}"},
        "ks4": {"apply_yg":  6, "max_in_phase": 11, "applying_for": "Year 7",
                "deadline_fmt": lambda yr: f"31 Oct {_acad_start + yr}"},
        "ks5": {"apply_yg": 11, "max_in_phase": 13, "applying_for": "Year 12",
                "deadline_fmt": lambda yr: f"typically Jan–Mar {_acad_start + yr + 1}"},
    }
    children = st.session_state.get("children", [])
    entry = _ENTRY.get(ks_key, {})
    apply_yg = entry.get("apply_yg")
    applying_for = entry.get("applying_for", "this phase")

    is_standard = False
    adm_when = ""
    for child in children:
        yg = child.get("year_group")
        if yg is None or apply_yg is None:
            continue
        if yg <= apply_yg:
            is_standard = True
            years_until = apply_yg - yg
            deadline = entry["deadline_fmt"](years_until)
            if years_until == 0:
                adm_when = f"applying for {applying_for} this cycle ({deadline})"
            else:
                adm_when = (
                    f"applying for {applying_for} in "
                    f"{years_until} year{'s' if years_until > 1 else ''} ({deadline})"
                )
            break

    if is_standard:
        adm_type_label = f"📋 **Standard admission** — {adm_when}"
        adm_distance_note = (
            "With standard admission, **where you live is usually the decisive factor**. "
            "For oversubscribed non-selective schools, places go to children who live closest "
            "(straight-line from home to school gate, after sibling and faith priorities). "
            "If you are not yet living near the school, your application will be assessed on your current address."
        )
    else:
        adm_type_label = "📝 **In-year admission** — joining mid-phase"
        adm_distance_note = (
            "With in-year admission, **distance is less decisive**. Schools must offer a place if they have a "
            "vacancy in the relevant year group — you do not compete against other applicants in an annual round. "
            "Apply directly to the school or the local authority. If a school is full, you can ask to be added "
            "to a waiting list, where proximity typically determines position."
        )
    st.markdown(adm_type_label)
    st.caption(adm_distance_note)

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
