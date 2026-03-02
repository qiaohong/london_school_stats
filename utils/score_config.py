"""
Shared attribute definitions for the custom composite score builder.
Each entry: (field_key, label, description, higher_is_better)
  higher_is_better=True  → high value is good
  higher_is_better=False → low value is good (e.g. absence)
  higher_is_better=None  → contextual / neutral
"""

SCORE_ATTRIBUTES: dict[str, list[tuple]] = {
    "ks2": [
        (
            "avg_progress",
            "Average Progress",
            "Average of reading, writing, and maths progress scores. Measures how much "
            "pupils improved compared to similar pupils nationally. 0 = national average; "
            "positive = above average.",
            True,
        ),
        (
            "pct_rwm_expected",
            "% Meeting Expected Standard (RWM)",
            "% of pupils achieving the expected standard in all of Reading, Writing, and Maths. "
            "National average ~65%.",
            True,
        ),
        (
            "pct_rwm_high",
            "% Achieving Higher Standard (RWM)",
            "% of pupils achieving the higher standard across Reading, Writing, and Maths. "
            "Nationally ~8–10%. Signals a strong academic culture.",
            True,
        ),
        (
            "absence_pct",
            "Attendance (low absence)",
            "Absence rate — lower is better. London average ~4.5%. Persistent absenteeism "
            "above 15% is a concern and may indicate school culture issues.",
            False,
        ),
        (
            "pct_fsm",
            "Free School Meals %",
            "% of pupils eligible for free school meals — a proxy for socioeconomic diversity "
            "of intake. Higher = more deprived/diverse intake. Neutral indicator; consider it "
            "context rather than quality.",
            None,
        ),
        (
            "pct_eal",
            "English as Additional Language %",
            "% of pupils whose first language is not English. London average ~40%. "
            "Higher = more linguistically diverse intake. Neutral indicator.",
            None,
        ),
        (
            "persistent_absence_pct",
            "Persistent Absence %",
            "% of pupils missing 10% or more of sessions — a stricter attendance measure. "
            "Lower is better. London average ~15%.",
            False,
        ),
        (
            "fsm_gap_rwm",
            "Disadvantage Gap (RWM)",
            "Attainment gap between FSM-eligible and non-FSM pupils in RWM. "
            "Smaller gap = more inclusive school. Lower is better.",
            False,
        ),
    ],
    "ks4": [
        (
            "progress8",
            "Progress 8",
            "DfE's headline secondary metric. Measures how much pupils improved across 8 "
            "subjects compared to similar pupils nationally. 0 = national average; "
            "+0.5 = strong performance; −0.5 = weak.",
            True,
        ),
        (
            "attainment8",
            "Attainment 8",
            "Average grade across 8 GCSE subjects (English, Maths, 3 EBacc subjects, "
            "3 open). London average ~50. Reflects absolute grade outcomes.",
            True,
        ),
        (
            "pct_grade5_eng_maths",
            "% Grade 5+ in English & Maths",
            "% achieving a strong pass (grade 5+) in both English Language and Maths GCSE. "
            "London average ~50%. The standard benchmark for further study eligibility.",
            True,
        ),
        (
            "pct_ebacc_5plus",
            "% EBacc at Grade 5+",
            "% achieving the English Baccalaureate at grade 5+ (English, Maths, 2 Sciences, "
            "History or Geography, a Language). Signals breadth of academic curriculum.",
            True,
        ),
        (
            "dest_pct_sixthform",
            "% Going to Sixth Form",
            "% of Year 11 leavers progressing to a sixth form or sixth-form college. Higher "
            "suggests a stronger academic culture and better post-16 preparation.",
            True,
        ),
        (
            "absence_pct",
            "Attendance (low absence)",
            "Absence rate — lower is better. London average ~5.5% absence.",
            False,
        ),
        (
            "persistent_absence_pct",
            "Persistent Absence %",
            "% of pupils missing 10% or more of sessions. Lower is better. "
            "London average ~20%.",
            False,
        ),
        (
            "pct_eal",
            "English as Additional Language %",
            "% of pupils whose first language is not English. London average ~40%. "
            "Neutral indicator of linguistic diversity.",
            None,
        ),
        (
            "fsm_gap_att8",
            "Disadvantage Gap (Attainment 8)",
            "Attainment 8 gap between FSM-eligible and non-FSM pupils. "
            "Smaller gap = more inclusive school. Lower is better.",
            False,
        ),
        (
            "dest_pct_neet",
            "% NEET after Year 11",
            "% of Year 11 leavers not in education, employment, or training. "
            "Lower is better. Signals pastoral support quality.",
            False,
        ),
        (
            "punching_above_weight",
            "Punching Above Weight",
            "1 if the school's Progress 8 score is above what would be predicted from its "
            "intake (contextual value-added). Signals a school doing more with its cohort "
            "than expected. 0 = not flagged.",
            True,
        ),
    ],
    "ks5": [
        (
            "alevel_value_added",
            "A-level Value Added",
            "How much students improve from GCSE baseline to A-level results compared to "
            "similar students nationally. 0 = average; positive = school adds value.",
            True,
        ),
        (
            "pct_aab_facilitating",
            "% AAB in Facilitating Subjects",
            "% of students achieving AAB or better with at least 2 in facilitating subjects "
            "(sciences, maths, languages, humanities). Key for Russell Group and competitive "
            "university entry.",
            True,
        ),
        (
            "dest_pct_he",
            "% Going to University",
            "% of students progressing to higher education. London average ~65–70%. "
            "Reflects aspirational culture and post-18 guidance quality.",
            True,
        ),
        (
            "absence_pct",
            "Attendance (low absence)",
            "Absence rate — lower is better.",
            False,
        ),
        (
            "pct_eal",
            "English as Additional Language %",
            "% of students whose first language is not English. Neutral indicator of "
            "linguistic diversity.",
            None,
        ),
        (
            "dest_pct_neet",
            "% NEET after Sixth Form",
            "% of students not in education, employment, or training after leaving. "
            "Lower is better.",
            False,
        ),
        (
            "pct_fsm",
            "Free School Meals %",
            "% of students eligible for free school meals. Neutral socioeconomic indicator.",
            None,
        ),
    ],
}


def fetch_top10_thresholds(ks_key: str, field_keys: list[str]) -> dict[str, tuple[float | None, float | None]]:
    """
    Return {field_key: (p10, p90)} — 10th and 90th percentile values from metrics_{ks_key}.
    p10 = the value at which only 10% of schools are lower (useful for lower-is-better attrs).
    p90 = the value at which only 10% of schools are higher (useful for higher-is-better attrs).
    """
    import sqlite3
    import os
    db_path = os.path.join(os.path.dirname(__file__), "..", "schools.db")
    table = f"metrics_{ks_key}"
    result: dict[str, tuple] = {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for key in field_keys:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {key} IS NOT NULL")
            n = cur.fetchone()[0]
            if n == 0:
                result[key] = (None, None)
                continue
            p10_offset = max(0, int(n * 0.10) - 1)
            p90_offset = max(0, int(n * 0.90) - 1)
            cur.execute(f"SELECT {key} FROM {table} WHERE {key} IS NOT NULL ORDER BY {key} LIMIT 1 OFFSET {p10_offset}")
            p10 = cur.fetchone()
            cur.execute(f"SELECT {key} FROM {table} WHERE {key} IS NOT NULL ORDER BY {key} LIMIT 1 OFFSET {p90_offset}")
            p90 = cur.fetchone()
            result[key] = (
                float(p10[0]) if p10 else None,
                float(p90[0]) if p90 else None,
            )
        except Exception:
            result[key] = (None, None)
    conn.close()
    return result


def fetch_london_bounds(ks_key: str, field_keys: list[str]) -> dict[str, tuple[float, float]]:
    """
    Query MIN and MAX for each field across all London schools in metrics_{ks_key}.
    Returns {field_key: (min_val, max_val)}.  Fields with no data are omitted.
    """
    import sqlite3
    import os
    db_path = os.path.join(os.path.dirname(__file__), "..", "schools.db")
    table = f"metrics_{ks_key}"
    bounds: dict[str, tuple[float, float]] = {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for key in field_keys:
        try:
            cur.execute(f"SELECT MIN({key}), MAX({key}) FROM {table}")
            row = cur.fetchone()
            if row and row[0] is not None and row[1] is not None:
                bounds[key] = (float(row[0]), float(row[1]))
        except Exception:
            pass  # field doesn't exist in this table
    conn.close()
    return bounds


def get_available_attributes(ks_keys: list[str]) -> list[tuple]:
    """Return deduplicated list of (field_key, label, desc, higher_is_better)
    for the given KS keys, in phase order."""
    seen: set[str] = set()
    result: list[tuple] = []
    for ks in ks_keys:
        for item in SCORE_ATTRIBUTES.get(ks, []):
            if item[0] not in seen:
                seen.add(item[0])
                result.append(item)
    return result


def attributes_for_ks(ks_key: str) -> set[str]:
    """Return the set of field keys defined for a specific ks_key."""
    return {item[0] for item in SCORE_ATTRIBUTES.get(ks_key, [])}
