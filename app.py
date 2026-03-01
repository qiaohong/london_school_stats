"""
London School Selector — interactive multi-step Streamlit app.
Run: venv_app/bin/streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="London School Selector",
    page_icon="🏫",
    layout="centered",
)

# --- Session state defaults ---
if "step" not in st.session_state:
    st.session_state.step = 1

# --- Progress bar ---
STEPS = ["Your situation", "Choose areas", "School criteria", "Shortlist", "Deep dive"]
step = st.session_state.step

st.title("London School Selector")
st.progress((step - 1) / (len(STEPS) - 1), text=f"Step {step} of {len(STEPS)}: {STEPS[step - 1]}")
st.divider()

# --- Route to current step ---
if step == 1:
    from steps.step1_input import render
    render()

elif step == 2:
    from steps.step2_la_select import render
    render()

elif step == 3:
    from steps.step3_criteria import render
    render()

elif step == 4:
    from steps.step4_shortlist import render
    render()

elif step == 5:
    from steps.step5_deepdive import render
    render()
