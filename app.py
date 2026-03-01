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

# --- Apple design system CSS ---
st.markdown("""
<style>
/* ── Font & antialiasing ─────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                 "SF Pro Display", "Helvetica Neue", Arial, sans-serif !important;
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
}

/* ── Background ──────────────────────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #ffffff !important;
}
[data-testid="block-container"] {
    max-width: 840px !important;
    padding-top: 2.5rem !important;
    padding-bottom: 5rem !important;
}

/* ── Typography ──────────────────────────────────────────────────────── */
h1 {
    font-size: 2.4rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    color: #1d1d1f !important;
    line-height: 1.08 !important;
}
h2 {
    font-size: 1.55rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: #1d1d1f !important;
    line-height: 1.15 !important;
}
h3 {
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    color: #1d1d1f !important;
}
p { color: #1d1d1f; line-height: 1.6; }

/* Captions / secondary text */
[data-testid="stCaptionContainer"] p,
.stCaption p,
small {
    color: #6e6e73 !important;
    font-size: 0.78rem !important;
    line-height: 1.5 !important;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
[role="progressbar"] {
    background: #e5e5ea !important;
    border-radius: 5px !important;
    height: 4px !important;
}
[role="progressbar"] > div,
[role="progressbar"] [style*="width"] {
    background: #0071e3 !important;
    border-radius: 5px !important;
}
[data-testid="stProgressBar"] > div {
    background: #e5e5ea !important;
    border-radius: 5px !important;
    height: 4px !important;
}
[data-testid="stProgressBar"] > div > div {
    background: #0071e3 !important;
    border-radius: 5px !important;
}

/* ── Divider ─────────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid #e5e5ea !important;
    margin: 2rem 0 !important;
}

/* ── Primary buttons ─────────────────────────────────────────────────── */
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: #0071e3 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 980px !important;
    padding: 0.52rem 1.35rem !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    letter-spacing: -0.005em !important;
    transition: background 0.2s ease !important;
    min-height: unset !important;
}
.stButton > button[kind="primary"]:hover {
    background: #0077ed !important;
    border: none !important;
}
.stButton > button[kind="primary"]:disabled {
    background: #b3d4f5 !important;
    color: #ffffff !important;
}

/* ── Secondary buttons ───────────────────────────────────────────────── */
.stButton > button[kind="secondary"],
button[data-testid="baseButton-secondary"] {
    background: transparent !important;
    color: #1d1d1f !important;
    border: 1px solid #d2d2d7 !important;
    border-radius: 980px !important;
    padding: 0.52rem 1.35rem !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    transition: background 0.2s ease, border-color 0.2s ease !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #f5f5f7 !important;
    border-color: #c7c7cc !important;
}

/* ── Link buttons ────────────────────────────────────────────────────── */
a[data-testid="stLinkButton"],
[data-testid="stLinkButton"] a {
    display: inline-block !important;
    background: #0071e3 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 980px !important;
    padding: 0.52rem 1.35rem !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    text-decoration: none !important;
}
a[data-testid="stLinkButton"]:hover {
    background: #0077ed !important;
}

/* ── Cards (st.container with border=True) ───────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #e5e5ea !important;
    border-radius: 18px !important;
    padding: 1.2rem 1.4rem !important;
    background: #fbfbfd !important;
    box-shadow: 0 1px 6px rgba(0, 0, 0, 0.05) !important;
    margin-bottom: 0.75rem !important;
}

/* ── Metrics ─────────────────────────────────────────────────────────── */
[data-testid="stMetricValue"] {
    font-size: 1.55rem !important;
    font-weight: 600 !important;
    color: #1d1d1f !important;
    letter-spacing: -0.02em !important;
    line-height: 1.1 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.68rem !important;
    font-weight: 500 !important;
    color: #6e6e73 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.78rem !important;
}

/* ── Text inputs ─────────────────────────────────────────────────────── */
.stTextInput input,
.stNumberInput input {
    border: 1px solid #d2d2d7 !important;
    border-radius: 10px !important;
    padding: 0.52rem 0.85rem !important;
    font-size: 0.88rem !important;
    background: #ffffff !important;
    color: #1d1d1f !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextInput input:focus,
.stNumberInput input:focus {
    border-color: #0071e3 !important;
    box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.12) !important;
    outline: none !important;
}

/* ── Selectbox ───────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    border: 1px solid #d2d2d7 !important;
    border-radius: 10px !important;
    background: #ffffff !important;
}

/* ── Multiselect ─────────────────────────────────────────────────────── */
[data-testid="stMultiSelect"] > div > div {
    border: 1px solid #d2d2d7 !important;
    border-radius: 10px !important;
    background: #ffffff !important;
}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: #e3f0fd !important;
    border-radius: 6px !important;
    color: #0071e3 !important;
}

/* ── Expander ────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #e5e5ea !important;
    border-radius: 12px !important;
    background: #fbfbfd !important;
    overflow: hidden !important;
}
[data-testid="stExpanderDetails"] {
    background: #fbfbfd !important;
}

/* ── Alerts ──────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: none !important;
    font-size: 0.875rem !important;
}

/* ── Slider ──────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
    background: #0071e3 !important;
}

/* ── Checkbox / Radio labels ─────────────────────────────────────────── */
[data-testid="stCheckbox"] label p,
[data-testid="stRadio"] label p {
    font-size: 0.88rem !important;
    color: #1d1d1f !important;
}

/* ── Markdown tables ─────────────────────────────────────────────────── */
table {
    border-collapse: collapse !important;
    width: 100% !important;
    font-size: 0.84rem !important;
}
th {
    background: #f5f5f7 !important;
    color: #6e6e73 !important;
    font-weight: 600 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    padding: 0.45rem 0.75rem !important;
    border-bottom: 1px solid #e5e5ea !important;
    text-align: left !important;
}
td {
    padding: 0.45rem 0.75rem !important;
    border-bottom: 1px solid #f0f0f0 !important;
    color: #1d1d1f !important;
}
tr:last-child td { border-bottom: none !important; }

/* ── Spinner ─────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: #6e6e73 !important; }
</style>
""", unsafe_allow_html=True)

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
