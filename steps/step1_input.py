"""
Step 1: Collect work postcode, commute preferences, and children's birth dates.
"""

import streamlit as st
from datetime import date
from utils.age_stage import birth_to_year_group, year_group_label, relevant_phases


_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_CURRENT_YEAR = date.today().year

_DEFAULT_POSTCODE = "N1C 4DB"

_PHASE_TO_KS = {
    "Primary (KS1/KS2)":    "ks2",
    "Secondary (KS3/KS4)":  "ks4",
    "Sixth Form (KS5)":     "ks5",
}


def _phase_admission_detail(ks_key: str, yg: int) -> tuple[str, str]:
    """
    Return (icon, detail_text) for a given phase and child's current year group.
    Handles both current-cycle and future standard admissions.
    """
    today = date.today()
    acad_start = today.year if today.month >= 9 else today.year - 1

    if ks_key == "ks2":
        if yg < 0:  # Nursery or pre-school — applying for Reception
            years_until = max(0, -1 - yg)
            dl_year = acad_start + years_until + 1
            if years_until == 0:
                return "📋", f"Standard admission for Reception — deadline ~15 Jan {dl_year}"
            return "📋", f"Standard admission for Reception in {years_until} year{'s' if years_until > 1 else ''} — deadline ~15 Jan {dl_year}"
        return "📝", "In-year admission — already in primary school; switching schools is a mid-phase transfer"

    if ks_key == "ks4":
        if yg <= 6:
            years_until = 6 - yg
            dl_year = acad_start + years_until
            if years_until == 0:
                return "📋", f"Standard admission for Year 7 — deadline 31 Oct {dl_year}"
            return "📋", f"Standard admission for Year 7 in {years_until} year{'s' if years_until > 1 else ''} — deadline 31 Oct {dl_year}"
        return "📝", "In-year admission — already in secondary school"

    if ks_key == "ks5":
        if yg <= 11:
            years_until = 11 - yg
            dl_year = acad_start + years_until + 1
            if years_until == 0:
                return "📋", f"Standard admission for Year 12 — deadline typically Jan–Mar {dl_year}"
            return "📋", f"Standard admission for Year 12 in {years_until} year{'s' if years_until > 1 else ''} — deadline typically Jan–Mar {dl_year}"
        return "📝", "In-year admission — already in sixth form"

    return "📝", "In-year admission"

_TECH_POSTCODES = """
| Company | Address | Postcode |
|---|---|---|
| Google | 6 Pancras Square, King's Cross | N1C 4AG |
| Meta | 21 Canal Reach, King's Cross | N1C 4DB |
| OpenAI | York House, 221 Pentonville Road | N1 9NL |
| Amazon | 1 Principal Place, Shoreditch | EC2A 2FA |
| Microsoft | 2 Kingdom Street, Paddington | W2 6BD |
| Spotify | 25 Argyll Street, Soho | W1F 7TS |
| Revolut | 30 South Colonnade, Canary Wharf | E14 5HX |
| DeepMind | 5 New Street Square, City | EC4A 3TW |
| Monzo | Broadwalk House, Appold Street | EC2A 2DA |
| JP Morgan | 25 Bank Street, Canary Wharf | E14 5JP |
"""


def render():
    st.header("Step 1 of 5 — Your situation")

    st.subheader("Where do you work?")

    with st.expander("London postcodes for major tech & finance employers"):
        st.markdown(_TECH_POSTCODES)

    postcode = st.text_input(
        "Work postcode",
        value=st.session_state.get("work_postcode", _DEFAULT_POSTCODE),
        placeholder="e.g. EC2A 4PX",
        help="We'll use this to estimate commute times to different areas of London.",
    )

    st.subheader("Commute preferences")
    col1, col2 = st.columns(2)
    with col1:
        commute_limit = st.slider(
            "Maximum commute time (minutes)",
            min_value=10,
            max_value=90,
            value=st.session_state.get("commute_limit", 40),
            step=5,
        )
    with col2:
        flex = st.radio(
            "How strictly should we apply this limit?",
            options=["Strict", "Flexible (+20%)"],
            index=0 if st.session_state.get("commute_flex", "Strict") == "Strict" else 1,
            help="Flexible adds 20% headroom (e.g. 8 min on a 40 min limit) to catch areas slightly over.",
        )

    st.subheader("Your children")
    st.caption(
        "We'll work out which school stages are relevant based on their age, "
        "looking at now and the next 3 years."
    )
    with st.expander("Key stages & admission types explained"):
        st.caption(
            "**KS1/KS2** = Primary (ages 5–11, Years 1–6)  ·  "
            "**KS3/KS4** = Secondary (ages 11–16, Years 7–11)  ·  "
            "**KS5** = Sixth Form (ages 16–18, Years 12–13)"
        )
        st.markdown(
            "| Year group | Admission type | What it means |\n"
            "|---|---|---|\n"
            "| Nursery / Reception | **Standard** | Applying for Reception in the main round — deadline ~15 Jan for Sept start |\n"
            "| Year 6 | **Standard** | Applying for Year 7 in the main round — deadline ~31 Oct for Sept start |\n"
            "| Year 11 | **Standard** | Applying for Year 12 / sixth form — deadline varies by school |\n"
            "| All other year groups | **In-year** | Joining mid-phase — apply directly to the school or LA for a mid-year place |"
        )

    num_children = st.number_input(
        "How many children?",
        min_value=1,
        max_value=3,
        value=st.session_state.get("num_children", 1),
        step=1,
    )

    children = []
    for i in range(int(num_children)):
        st.markdown(f"**Child {i + 1}**")
        prev = st.session_state.get("children", [])
        prev_child = prev[i] if i < len(prev) else {}

        col_m, col_y = st.columns(2)
        with col_m:
            birth_month = st.selectbox(
                "Birth month",
                options=list(range(1, 13)),
                format_func=lambda m: _MONTHS[m - 1],
                index=prev_child.get("birth_month", 1) - 1,
                key=f"child_{i}_month",
            )
        with col_y:
            birth_year = st.number_input(
                "Birth year",
                min_value=_CURRENT_YEAR - 19,
                max_value=_CURRENT_YEAR - 2,
                value=prev_child.get("birth_year", _CURRENT_YEAR - 7),
                step=1,
                key=f"child_{i}_year",
            )

        # Compute raw year group (allows values below -1 for pre-school children)
        _today = date.today()
        _acad_start = _today.year if _today.month >= 9 else _today.year - 1
        _correction = 1 if birth_month > 8 else 0
        raw_yg = (_acad_start - int(birth_year) - _correction) - 4

        yg = birth_to_year_group(birth_year, birth_month)  # None if raw_yg < -1

        if yg is not None:
            phases = relevant_phases(birth_year, birth_month)
            if phases:
                label_str = " → ".join(dict.fromkeys(p["phase"] for p in phases))
                st.success(f"Currently {year_group_label(yg)} — stages to consider: **{label_str}**")
                seen_ks = []
                for p in phases:
                    ks = _PHASE_TO_KS.get(p["phase"])
                    if ks and ks not in seen_ks:
                        seen_ks.append(ks)
                        phase_label = {"ks2": "Primary", "ks4": "Secondary", "ks5": "Sixth form"}[ks]
                        icon, detail = _phase_admission_detail(ks, yg)
                        st.markdown(f"{icon} **{phase_label}:** {detail}.")
        elif raw_yg < -1:
            # Not yet school age — synthesise KS2 phase so the app can show primary schools
            yg = raw_yg
            phases = [{"phase": "Primary (KS1/KS2)", "year_group": 0, "label": "Reception",
                       "years_from_now": -1 - raw_yg + 1, "transition": None}]
            st.info("Not yet school age — will show primary school options for when they start.")
            icon, detail = _phase_admission_detail("ks2", yg)
            st.markdown(f"{icon} **Primary:** {detail}.")
        else:
            st.info("Please enter a valid birth year.")
            phases = []

        children.append({
            "birth_year": int(birth_year),
            "birth_month": birth_month,
            "year_group": yg,
            "phases": phases,
        })

    # Validation
    postcode_ok = len(postcode.strip()) >= 5
    children_ok = all(bool(c["phases"]) for c in children)
    if not postcode_ok:
        st.warning("Please enter a full UK postcode (e.g. EC2A 4PX).")

    if st.button("Next: Choose areas →", type="primary", disabled=not (postcode_ok and children_ok)):
        flex_pct = 0.20 if flex == "Flexible (+20%)" else 0.0
        st.session_state.work_postcode = postcode.strip().upper()
        st.session_state.commute_limit = commute_limit
        st.session_state.commute_flex = flex
        st.session_state.flex_minutes = int(commute_limit * flex_pct)
        st.session_state.num_children = int(num_children)
        st.session_state.children = children
        st.session_state.step = 2
        st.rerun()
