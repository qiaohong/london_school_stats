"""
Step 3: Collect school criteria — Ofsted, type, admissions, gender, faith, score floor.
"""

import streamlit as st
from utils.db import FAITH_GROUPS

# Display order for Ofsted
OFSTED_OPTIONS = ["Outstanding", "Good", "Requires improvement", "Inadequate"]

# School type options (MINORGROUP values in DB)
TYPE_OPTIONS = ["Academy", "Maintained school", "College", "Independent school"]

# Faith group display labels (keys from FAITH_GROUPS)
FAITH_OPTIONS = list(FAITH_GROUPS.keys())


def _phase_label(ks_keys: list[str]) -> str:
    mapping = {"ks2": "Primary", "ks4": "Secondary", "ks5": "Sixth Form"}
    return " + ".join(mapping[k] for k in ks_keys if k in mapping)


def render():
    st.header("Step 3 of 5 — School criteria")

    las = [la["la_name"] for la in st.session_state.get("selected_las", [])]
    ks_keys = st.session_state.get("ks_keys", ["ks4"])
    phase_str = _phase_label(ks_keys)

    st.caption(
        f"Searching **{phase_str}** schools in: **{', '.join(las)}**. "
        "Adjust these filters or keep the defaults."
    )

    prev = st.session_state.get("criteria", {})

    # ── Ofsted ──────────────────────────────────────────────────────────────
    st.subheader("Ofsted rating")
    ofsted_default = prev.get("ofsted_ratings", ["Outstanding", "Good"])
    ofsted_ratings = st.multiselect(
        "Include schools rated:",
        options=OFSTED_OPTIONS,
        default=ofsted_default,
        help="Ofsted inspects schools roughly every 4 years. ~6% of London schools are Outstanding.",
    )
    include_no_ofsted = st.checkbox(
        "Also include schools with no recent Ofsted rating",
        value=prev.get("include_no_ofsted", True),
        help="Some schools haven't been inspected recently (e.g. new academies, sixth form colleges).",
    )

    # ── School type ──────────────────────────────────────────────────────────
    st.subheader("School type")
    type_default = prev.get("school_types", ["Academy", "Maintained school"])
    school_types = st.multiselect(
        "Include school types:",
        options=TYPE_OPTIONS,
        default=type_default,
        help=(
            "**Academy**: independently run, state-funded. "
            "**Maintained**: run by the local authority. "
            "**College**: FE/sixth-form colleges (KS5 only). "
            "**Independent**: fee-paying (private)."
        ),
    )

    # ── Admissions ──────────────────────────────────────────────────────────
    st.subheader("Admissions")
    col1, col2 = st.columns(2)
    with col1:
        admpol_options = ["Any", "Non-selective", "Selective"]
        admpol_default = prev.get("admpol", "Non-selective")
        admpol = st.selectbox(
            "Admissions policy",
            options=admpol_options,
            index=admpol_options.index(admpol_default),
            help=(
                "**Selective**: entrance exam required (grammar schools). "
                "**Non-selective**: no exam; typically allocated by distance or faith."
            ),
        )
    with col2:
        gender_options = ["Any", "Mixed", "Girls", "Boys"]
        gender_default = prev.get("gender", "Any")
        gender = st.selectbox(
            "School gender",
            options=gender_options,
            index=gender_options.index(gender_default),
        )

    # ── Religious character ──────────────────────────────────────────────────
    st.subheader("Religious character")
    faith_default = prev.get("faith_groups", list(FAITH_GROUPS.keys()))  # all by default
    faith_groups = st.multiselect(
        "Include schools with these religious characters:",
        options=FAITH_OPTIONS,
        default=faith_default,
        help=(
            "Faith schools may give priority to applicants of that faith in admissions. "
            "Select all to see every school."
        ),
    )

    # ── Composite score ──────────────────────────────────────────────────────
    st.subheader("Minimum performance score")
    min_score = st.slider(
        "Composite score floor (0 = all schools, 50 = London average, 75 = top quarter)",
        min_value=0,
        max_value=90,
        value=prev.get("min_score", 40),
        step=5,
        help=(
            "Our composite score (0–100) combines progress, attainment, attendance, "
            "and destinations data. 50 = London median."
        ),
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
            st.session_state.step = 2
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
                "min_score": min_score,
            }
            # Clear any cached shortlist so step 4 re-queries
            st.session_state.pop("shortlist_results", None)
            st.session_state.step = 4
            st.rerun()
