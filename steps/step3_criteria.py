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

    # ── Admissions ──────────────────────────────────────────────────────────
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

    # ── Composite score ──────────────────────────────────────────────────────
    st.subheader("Minimum performance score")
    st.caption(
        "Our composite score (0–100) is a weighted combination of progress, attainment, "
        "attendance and destinations — percentile-ranked within London. "
        "**50 = London median. 75 = top 25%.** Missing data is imputed at 50. "
        "Weights: KS2 — progress 40%, RWM attainment 30%, absence 15%, higher attainment 15%. "
        "KS4 — Progress 8 35%, grade 5+ E&M 25%, absence 15%, destinations 15%, EBacc 10%. "
        "KS5 — A-level VA 40%, AAB facilitating 25%, HE destinations 25%, absence 10%."
    )
    min_score = st.slider(
        "Minimum composite score",
        min_value=0,
        max_value=90,
        value=prev.get("min_score", 40),
        step=5,
    )

    # ── Validation & navigation ───────────────────────────────────────────────
    st.divider()
    warn = []
    if not ofsted_ratings and not include_no_ofsted:
        warn.append("Select at least one Ofsted rating (or allow schools with no rating).")
    if not school_types:
        warn.append("Select at least one school type.")

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
                "faith_groups": list(FAITH_GROUPS.keys()),  # always include all faiths
                "min_score": min_score,
            }
            st.session_state.pop("shortlist_results", None)
            st.session_state.step = 4
            st.rerun()
