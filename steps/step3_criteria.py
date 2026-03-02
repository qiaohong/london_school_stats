"""
Step 3: Collect school criteria — Ofsted, type, admissions, gender, score floor.
Religion filter removed; all faith types included by default.
"""

import streamlit as st
from utils.db import FAITH_GROUPS

OFSTED_OPTIONS = ["Outstanding", "Good", "Requires improvement", "Inadequate"]
TYPE_OPTIONS = ["Academy", "Maintained school", "College", "Independent school"]


def _phase_label(ks_keys: list[str]) -> str:
    mapping = {"ks2": "Primary", "ks4": "Secondary", "ks5": "Sixth Form"}
    return " + ".join(mapping[k] for k in ks_keys if k in mapping)


def render():
    st.header("Step 4 of 6 — School criteria")

    las = [la["la_name"] for la in st.session_state.get("selected_las", [])]
    ks_keys = st.session_state.get("ks_keys", ["ks4"])
    phase_str = _phase_label(ks_keys)

    col_info, col_change = st.columns([4, 1])
    with col_info:
        st.caption(
            f"Searching **{phase_str}** schools in: **{', '.join(las)}**. "
            "Adjust these filters or keep the defaults."
        )
    with col_change:
        if st.button("Change boroughs"):
            st.session_state.step = 3
            st.rerun()

    prev = st.session_state.get("criteria", {})

    # ── Ofsted ──────────────────────────────────────────────────────────────
    st.subheader("Ofsted rating")
    st.caption(
        "Ofsted (Office for Standards in Education) inspects schools on a 4-point scale. "
        "Inspections typically happen every 4–5 years; ratings can change significantly. "
        "Around 6% of London schools are Outstanding, 66% Good, 22% Requires improvement, 6% Inadequate. "
        "Source: DfE school information file (ratings from 2022–23; some may be stale)."
    )
    ofsted_default = prev.get("ofsted_ratings", ["Outstanding", "Good"])
    ofsted_ratings = st.multiselect(
        "Include schools rated:",
        options=OFSTED_OPTIONS,
        default=ofsted_default,
    )
    include_no_ofsted = st.checkbox(
        "Also include schools with no Ofsted rating on record",
        value=prev.get("include_no_ofsted", True),
        help=(
            "~4% of schools in scope have no Ofsted record — typically new academies, "
            "recently opened free schools, or sixth-form colleges not subject to standard inspection."
        ),
    )

    # ── Admissions & gender ──────────────────────────────────────────────────
    st.subheader("Admissions & gender")
    col1, col2 = st.columns(2)
    with col1:
        st.caption(
            "**Selective**: school sets its own entrance exam (11+ for grammar schools, "
            "audition for performing arts). Places awarded by exam score, not proximity. "
            "**Non-selective**: no entrance exam; places typically allocated by "
            "distance (straight-line from home to school gate), sibling priority, or faith criteria. "
            "The `ADMPOL` field in DfE data is the school's registered policy."
        )
        admpol_options = ["Any", "Non-selective", "Selective"]
        admpol_default = prev.get("admpol", "Non-selective")
        admpol = st.selectbox(
            "Admissions policy",
            options=admpol_options,
            index=admpol_options.index(admpol_default),
        )
    with col2:
        st.caption(
            "**Mixed**: co-educational (boys and girls). "
            "**Single-sex schools** (Boys or Girls) are relatively rare in London — "
            "around 10% of secondaries. "
            "Source: `GENDER` field in DfE school information data."
        )
        gender_options = ["Any", "Mixed", "Girls", "Boys"]
        gender_default = prev.get("gender", "Any")
        gender = st.selectbox(
            "School gender",
            options=gender_options,
            index=gender_options.index(gender_default),
        )

    # ── School type ──────────────────────────────────────────────────────────
    st.subheader("School type")
    st.caption(
        "**Academy**: state-funded but independently run, outside local authority control. "
        "May set its own term dates, uniform and curriculum (within national requirements). "
        "**Maintained school**: run and funded by the local authority; follows standard LA policies. "
        "**College**: further education or sixth-form college (relevant for KS5 only); "
        "not inspected by Ofsted under the same framework as schools. "
        "**Independent**: fee-paying private school; DfE data coverage is partial for this group."
    )
    type_default = prev.get("school_types", ["Academy", "Maintained school"])
    school_types = st.multiselect(
        "Include school types:",
        options=TYPE_OPTIONS,
        default=type_default,
    )

    # ── Religion ─────────────────────────────────────────────────────────────
    st.subheader("Religious character")
    st.caption(
        "Faith schools may give admissions priority to families of that faith. "
        "Around 30% of London schools have a religious character. "
        "Select all to include every school regardless of faith."
    )
    faith_default = prev.get("faith_groups", list(FAITH_GROUPS.keys()))
    faith_groups = st.multiselect(
        "Include schools with religious character:",
        options=list(FAITH_GROUPS.keys()),
        default=faith_default,
    )

    # ── Number of schools ────────────────────────────────────────────────────
    st.subheader("Number of schools to show")
    st.caption(
        "Schools are ranked by your custom score (if set in Step 2) or the system composite score. "
        "The shortlist will show the top N schools passing your other filters above."
    )
    max_schools = st.number_input(
        "Maximum schools to show per phase",
        min_value=5,
        max_value=100,
        value=prev.get("max_schools", 20),
        step=5,
    )

    # ── Validation & navigation ───────────────────────────────────────────────
    st.divider()
    warn = []
    if not ofsted_ratings and not include_no_ofsted:
        warn.append("Select at least one Ofsted rating (or allow schools with no rating).")
    if not school_types:
        warn.append("Select at least one school type.")
    if not faith_groups:
        warn.append("Select at least one religious character option.")

    for w in warn:
        st.warning(w)

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 3
            st.rerun()
    with col_next:
        if st.button("Next: See your shortlist →", type="primary", disabled=bool(warn)):
            st.session_state.criteria = {
                "ofsted_ratings": ofsted_ratings,
                "include_no_ofsted": include_no_ofsted,
                "school_types": school_types,
                "admpol": admpol,
                "gender": gender,
                "faith_groups": faith_groups,
                "max_schools": int(max_schools),
            }
            st.session_state.pop("shortlist_results", None)
            st.session_state.step = 5
            st.rerun()
