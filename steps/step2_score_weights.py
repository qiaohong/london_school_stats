"""
Step 2: Build your custom school score.

Users pick up to 5 school attributes and assign weights that sum to 100.
The resulting score_weights dict is stored in session state and used in
subsequent steps to compute a custom composite score per school.
"""

import os
import sqlite3
import streamlit as st
from utils.age_stage import phases_to_ks_keys
from utils.score_config import get_available_attributes, fetch_london_bounds, fetch_top10_thresholds, attributes_for_ks

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "schools.db")


def _all_london_scores(
    ks_keys: list[str],
    weights: dict[str, int],
    directions: dict[str, bool],
    binary_flags: dict[str, bool] | None = None,
) -> list[float]:
    """
    Compute the custom score for every London school in the relevant phase tables.
    Uses the same London-wide min/max bounds as the shortlist scoring.
    """
    binary_flags = binary_flags or {}
    scores: list[float] = []
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()

    for ks_key in ks_keys:
        valid_keys = attributes_for_ks(ks_key)
        applicable = {k: v for k, v in weights.items() if k in valid_keys}
        if not applicable:
            continue
        total_weight = sum(applicable.values())
        if total_weight == 0:
            continue

        bounds_key = f"_london_bounds_{ks_key}"
        if bounds_key not in st.session_state:
            st.session_state[bounds_key] = fetch_london_bounds(ks_key, list(attributes_for_ks(ks_key)))
        bounds = st.session_state[bounds_key]

        top10_key = f"_london_top10_{ks_key}"
        if top10_key not in st.session_state:
            st.session_state[top10_key] = fetch_top10_thresholds(ks_key, list(attributes_for_ks(ks_key)))
        top10 = st.session_state[top10_key]

        field_list = ", ".join(applicable.keys())
        cur.execute(f"SELECT {field_list} FROM metrics_{ks_key}")

        for row in cur.fetchall():
            score_sum = 0.0
            for i, key in enumerate(applicable.keys()):
                val = row[i]
                if binary_flags.get(key):
                    p10, p90 = top10.get(key, (None, None))
                    hib = directions.get(key, True)
                    if val is None:
                        norm = 0.0
                    elif hib:
                        norm = 1.0 if (p90 is not None and val >= p90) else 0.0
                    else:
                        norm = 1.0 if (p10 is not None and val <= p10) else 0.0
                else:
                    lo_hi = bounds.get(key)
                    if lo_hi is None or val is None:
                        norm = 0.5
                    else:
                        lo, hi = lo_hi
                        norm = 0.5 if hi == lo else (val - lo) / (hi - lo)
                    if directions.get(key) is False:
                        norm = 1.0 - norm
                norm = max(0.0, min(1.0, norm))
                score_sum += norm * applicable[key]
            scores.append(score_sum / total_weight * 100)

    conn.close()
    return scores

_MAX_ATTRIBUTES = 5


def _get_ks_keys() -> list[str]:
    ks_keys = st.session_state.get("ks_keys", [])
    if not ks_keys:
        for child in st.session_state.get("children", []):
            for k in phases_to_ks_keys(child.get("phases", [])):
                if k not in ks_keys:
                    ks_keys.append(k)
    return ks_keys


def render():
    st.header("Step 2 of 6 — Build your school score")
    st.caption(
        "Our composite score ranks schools across **progress, attainment, attendance, "
        "and destinations**. Here you can customise it: pick up to **5 attributes** "
        "that matter most to you and assign each a weight. "
        "**Weights must sum to exactly 100.**"
    )

    ks_keys = _get_ks_keys()
    available = get_available_attributes(ks_keys)

    if not available:
        st.warning("No attributes available — please go back and check your child's details.")
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
        return

    prev_weights = st.session_state.get("score_weights", {})
    prev_directions = st.session_state.get("score_weight_directions", {})
    prev_binary = st.session_state.get("score_weight_binary", {})

    # Pre-load top-10% thresholds for all ks_keys (cached per ks_key)
    top10_by_ks: dict[str, dict] = {}
    for ks_key in ks_keys:
        cache_key = f"_london_top10_{ks_key}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = fetch_top10_thresholds(ks_key, list(attributes_for_ks(ks_key)))
        top10_by_ks[ks_key] = st.session_state[cache_key]

    def _get_threshold(field_key: str, hib_effective: bool) -> float | None:
        """Return the top-10% threshold for a field (p90 for higher-is-better, p10 for lower-is-better)."""
        for ks_key in ks_keys:
            t = top10_by_ks.get(ks_key, {}).get(field_key)
            if t is not None:
                p10, p90 = t
                return p90 if hib_effective else p10
        return None

    def _fmt_threshold(val) -> str:
        if val is None:
            return "n/a"
        if isinstance(val, float) and abs(val) < 10:
            return f"{val:+.2f}" if val < 0 else f"{val:.2f}"
        return f"{val:.1f}"

    # ── Attribute selection ──────────────────────────────────────────────────
    st.subheader("Choose attributes")
    st.caption(f"Select up to {_MAX_ATTRIBUTES} metrics to include in your score.")

    selected_keys: list[str] = []
    user_directions: dict[str, bool] = {}  # resolved directions including user choices for contextual
    user_binary: dict[str, bool] = {}  # whether each attribute uses binary top-10% mode

    for field_key, label, desc, higher_is_better in available:
        with st.container(border=True):
            col_check, col_text = st.columns([1, 9])
            with col_check:
                checked = st.checkbox(
                    "Select",
                    value=(field_key in prev_weights),
                    key=f"attr_{field_key}",
                    label_visibility="collapsed",
                )
            with col_text:
                if higher_is_better is True:
                    st.markdown(f"**{label}** &nbsp; `↑ higher is better`")
                    st.caption(desc)
                    user_directions[field_key] = True
                elif higher_is_better is False:
                    st.markdown(f"**{label}** &nbsp; `↓ lower is better`")
                    st.caption(desc)
                    user_directions[field_key] = False
                else:
                    # Contextual — ask the user which direction they prefer
                    st.markdown(f"**{label}**")
                    st.caption(desc)
                    prev_dir = prev_directions.get(field_key, True)
                    prev_choice = "Higher is better" if prev_dir else "Lower is better"
                    choice = st.radio(
                        "Which direction is better for you?",
                        options=["Higher is better", "Lower is better"],
                        index=0 if prev_choice == "Higher is better" else 1,
                        key=f"dir_{field_key}",
                        horizontal=True,
                    )
                    user_directions[field_key] = (choice == "Higher is better")

                # Binary flag option
                hib_eff = user_directions[field_key]
                threshold_val = _get_threshold(field_key, hib_eff)
                threshold_str = _fmt_threshold(threshold_val)
                qualifier = "≥" if hib_eff else "≤"
                top10_label = f"Binary (top 10% only — {qualifier} {threshold_str})"

                prev_is_binary = prev_binary.get(field_key, False)
                mode = st.radio(
                    "Scoring mode",
                    options=["Numeric score", top10_label],
                    index=1 if prev_is_binary else 0,
                    key=f"binary_{field_key}",
                    horizontal=True,
                    help=(
                        "**Numeric**: score = how far the school is across the London range for this metric. "
                        f"**Binary**: score = 1 if school is in the top 10% of London schools ({qualifier} {threshold_str}), else 0."
                    ),
                )
                user_binary[field_key] = (mode == top10_label)

        if checked:
            selected_keys.append(field_key)

    too_many = len(selected_keys) > _MAX_ATTRIBUTES
    if too_many:
        st.warning(f"Please select no more than {_MAX_ATTRIBUTES} attributes ({len(selected_keys)} selected).")

    # ── Weight assignment ────────────────────────────────────────────────────
    weights: dict[str, int] = {}
    total = 0

    if selected_keys and not too_many:
        st.divider()
        st.subheader("Assign weights")
        st.caption(
            "Set how much each attribute contributes to the final score. "
            "Adjust the sliders until the total reaches **100**."
        )

        # Build a lookup for labels
        label_map = {fk: lbl for fk, lbl, _, _ in available}

        default_weight = max(5, 100 // len(selected_keys))
        cols = st.columns(len(selected_keys))
        for col, field_key in zip(cols, selected_keys):
            with col:
                default = prev_weights.get(field_key, default_weight)
                w = st.number_input(
                    label_map.get(field_key, field_key),
                    min_value=0,
                    max_value=100,
                    value=default,
                    step=1,
                    key=f"w_{field_key}",
                )
                weights[field_key] = int(w)

        total = sum(weights.values())
        remaining = 100 - total

        col_total, col_hint = st.columns([1, 2])
        with col_total:
            if total == 100:
                st.success(f"Total: **{total} / 100** ✓")
            else:
                st.error(f"Total: **{total} / 100**")
        with col_hint:
            if total != 100 and selected_keys:
                if remaining > 0:
                    st.caption(f"Add **{remaining}** more to reach 100.")
                else:
                    st.caption(f"Remove **{-remaining}** to reach 100.")

    # ── Distribution chart ───────────────────────────────────────────────────
    if total == 100 and selected_keys and not too_many:
        import pandas as pd
        import altair as alt

        st.divider()
        st.subheader("Score distribution — all London schools")
        st.caption(
            "How all London schools are distributed on your custom score. "
            "Use this to sense-check your weights: a very skewed distribution "
            "may mean one attribute is dominating."
        )

        dist_cache_key = (
            tuple(sorted(weights.items())),
            tuple(sorted((k, v) for k, v in user_directions.items() if k in weights)),
            tuple(sorted((k, v) for k, v in user_binary.items() if k in weights)),
            tuple(ks_keys),
        )
        if st.session_state.get("_score_dist_key") != dist_cache_key:
            with st.spinner("Computing scores for all London schools…"):
                all_scores = _all_london_scores(ks_keys, weights, user_directions, user_binary)
            st.session_state._score_dist_scores = all_scores
            st.session_state._score_dist_key = dist_cache_key

        all_scores = st.session_state.get("_score_dist_scores", [])
        if all_scores:
            df = pd.DataFrame({"score": all_scores})
            chart = (
                alt.Chart(df)
                .mark_bar(color="#0071e3", opacity=0.85, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                .encode(
                    x=alt.X("score:Q", bin=alt.Bin(maxbins=25), title="Custom score (0–100)"),
                    y=alt.Y("count():Q", title="Number of schools"),
                    tooltip=[
                        alt.Tooltip("score:Q", bin=alt.Bin(maxbins=25), title="Score range"),
                        alt.Tooltip("count():Q", title="Schools"),
                    ],
                )
                .properties(height=220)
                .configure_axis(grid=False)
                .configure_view(strokeWidth=0)
            )
            st.altair_chart(chart, use_container_width=True)
            st.caption(f"{len(all_scores):,} schools across {len(ks_keys)} phase(s).")

    # ── Navigation ───────────────────────────────────────────────────────────
    st.divider()
    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
    with col_next:
        can_proceed = (
            len(selected_keys) >= 1
            and not too_many
            and total == 100
        )
        if st.button("Next: Choose areas →", type="primary", disabled=not can_proceed):
            st.session_state.score_weights = weights
            # Use user-chosen directions (covers contextual attributes too)
            st.session_state.score_weight_directions = {k: user_directions.get(k, True) for k in weights}
            st.session_state.score_weight_binary = {k: user_binary.get(k, False) for k in weights}
            st.session_state.step = 3
            st.rerun()
