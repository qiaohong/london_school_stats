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

        yg = birth_to_year_group(birth_year, birth_month)
        if yg is not None:
            phases = relevant_phases(birth_year, birth_month)
            if phases:
                label_str = " → ".join(dict.fromkeys(p["phase"] for p in phases))
                st.success(f"Currently {year_group_label(yg)} — stages to consider: **{label_str}**")
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
    children_ok = all(c["year_group"] is not None for c in children)
    if not postcode_ok:
        st.warning("Please enter a full UK postcode (e.g. EC2A 4PX).")
    if not children_ok:
        st.warning("One or more children's birth dates couldn't be resolved to a year group.")

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
