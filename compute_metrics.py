"""
compute_metrics.py — Compute interesting data points and comparisons from London school data.

Outputs written to schools.db:
  metrics_ks4    — Secondary school metrics (one row per school, latest year + trends + composite)
  metrics_ks2    — Primary school metrics
  metrics_ks5    — Sixth form metrics
  metrics_la     — Borough-level averages (all phases)
  metrics_type   — School type averages (all phases)
"""

import sqlite3
import numpy as np
import pandas as pd

DB_PATH = "schools.db"

SUPP = {"SUPP", "NE", "NP", "LOW"}
YEARS = ["2022-2023", "2023-2024", "2024-2025"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def to_num(df, cols):
    """Convert listed columns to numeric, stripping % signs and suppression markers."""
    for c in cols:
        if c in df.columns:
            s = df[c].astype(str).str.strip().str.rstrip("%")
            s[s.isin(SUPP)] = np.nan
            df[c] = pd.to_numeric(s, errors="coerce")
    return df


def latest_year_per_school(df, metric_cols, id_col="URN"):
    """
    For each school (URN), keep only the most recent academic year that has
    at least one non-null metric value. Returns one row per school.
    """
    df = df.copy()
    df["_year_rank"] = df["academic_year"].map(
        {y: i for i, y in enumerate(YEARS)}
    )
    # Sort descending so most recent year comes first
    df = df.sort_values([id_col, "_year_rank"], ascending=[True, False])
    # Drop rows where ALL metric cols are null
    df["_any_metric"] = df[metric_cols].notna().any(axis=1)
    df = df[df["_any_metric"]]
    # Keep first (most recent) row per school
    df = df.drop_duplicates(subset=[id_col], keep="first")
    return df.drop(columns=["_year_rank", "_any_metric"])


def pct_rank_0_100(series):
    """Percentile rank within London (0=worst, 100=best). Higher is always better."""
    return series.rank(pct=True, na_option="keep") * 100


def pct_rank_inverted(series):
    """Percentile rank where lower raw value = better score (e.g. absence)."""
    return (1 - series.rank(pct=True, na_option="keep")) * 100


def save(conn, df, table):
    df.to_sql(table, conn, if_exists="replace", index=False)
    print(f"  {table}: {len(df):,} rows, {len(df.columns)} cols")


# ── Load base tables ──────────────────────────────────────────────────────────

def norm_urn(df):
    """Coerce URN column to nullable Int64 so all tables merge cleanly."""
    if "URN" in df.columns:
        df["URN"] = pd.to_numeric(df["URN"], errors="coerce").astype("Int64")
    return df


def load_tables(conn):
    tables = {
        "schools":  "SELECT * FROM schools",
        "ks4":      "SELECT * FROM ks4_results",
        "ks2":      "SELECT * FROM ks2_results",
        "ks5":      "SELECT * FROM ks5_results",
        "census":   "SELECT * FROM census",
        "absences": "SELECT * FROM absences",
        "ks4dest":  "SELECT * FROM ks4_pupil_destinations",
        "ks5dest":  "SELECT * FROM ks5_student_destinations",
    }
    return tuple(norm_urn(pd.read_sql(q, conn)) for q in tables.values())


# ── Prep: latest-year census and absence per URN ──────────────────────────────

def prep_census(census):
    census = to_num(census, ["PNUMFSMEVER", "PNUMEAL", "PSENELSE", "PSENELK", "NOR"])
    census = latest_year_per_school(census, ["PNUMFSMEVER", "PNUMEAL"], id_col="URN")
    return census[["URN", "NOR", "PNUMFSMEVER", "PNUMEAL", "PSENELSE", "PSENELK"]].rename(columns={
        "NOR": "census_total_pupils",
        "PNUMFSMEVER": "pct_fsm",
        "PNUMEAL": "pct_eal",
        "PSENELSE": "pct_sen_support",
        "PSENELK": "pct_sen_ehcp",
    })


def prep_absences(absences):
    absences = to_num(absences, ["PERCTOT", "PPERSABS10"])
    # Latest year available (only 2 years for abs)
    absences = latest_year_per_school(absences, ["PERCTOT", "PPERSABS10"], id_col="URN")
    return absences[["URN", "PERCTOT", "PPERSABS10", "academic_year"]].rename(columns={
        "PERCTOT": "absence_pct",
        "PPERSABS10": "persistent_absence_pct",
        "academic_year": "absence_year",
    })


# ── KS4 metrics ───────────────────────────────────────────────────────────────

def build_ks4(ks4, schools, census_prep, abs_prep, ks4dest, conn):
    print("\nBuilding KS4 metrics...")

    METRICS = ["ATT8SCR", "P8MEA", "P8CILOW", "P8CIUPP",
               "PTL2BASICS_94", "PTL2BASICS_95", "PTEBACC_94", "PTEBACC_95", "TPUP",
               "ATT8SCR_FSM6CLA1A", "ATT8SCR_NFSM6CLA1A", "DIFFN_ATT8",
               "P8MEA_FSM6CLA1A", "P8MEA_NFSM6CLA1A", "DIFFN_P8MEA"]

    ks4 = to_num(ks4, METRICS)

    # ── Trend: change in P8, ATT8, basics5 from earliest to latest year ──────
    trend_cols = ["P8MEA", "ATT8SCR", "PTL2BASICS_95"]
    ks4_sorted = ks4.sort_values(["URN", "academic_year"])
    trends = []
    for urn, grp in ks4_sorted.groupby("URN"):
        grp = grp.dropna(subset=["P8MEA"])
        if len(grp) >= 2:
            first, last = grp.iloc[0], grp.iloc[-1]
            trends.append({
                "URN": urn,
                "p8_trend":       round(last["P8MEA"] - first["P8MEA"], 3),
                "att8_trend":     round(last["ATT8SCR"] - first["ATT8SCR"], 2)
                                  if pd.notna(last["ATT8SCR"]) and pd.notna(first["ATT8SCR"]) else np.nan,
                "basics5_trend":  round(last["PTL2BASICS_95"] - first["PTL2BASICS_95"], 2)
                                  if pd.notna(last["PTL2BASICS_95"]) and pd.notna(first["PTL2BASICS_95"]) else np.nan,
                "trend_from_year": first["academic_year"],
                "trend_to_year":   last["academic_year"],
            })
    trends_df = pd.DataFrame(trends)

    # ── Latest year metrics ───────────────────────────────────────────────────
    # P8MEA is null in 2024-2025 provisional — get it from the most recent year that has it
    P8_COLS = ["P8MEA", "P8CILOW", "P8CIUPP",
               "P8MEA_FSM6CLA1A", "P8MEA_NFSM6CLA1A", "DIFFN_P8MEA"]
    ATT_COLS = [c for c in METRICS if c not in P8_COLS]

    ks4_has_p8 = ks4[ks4["P8MEA"].notna()]
    p8_latest  = latest_year_per_school(ks4_has_p8, P8_COLS, id_col="URN")[["URN"] + P8_COLS]
    df = latest_year_per_school(ks4, ATT_COLS, id_col="URN")
    # Drop P8 cols that came along for the ride before re-adding from p8_latest
    df = df.drop(columns=[c for c in P8_COLS if c in df.columns], errors="ignore")
    df = df.merge(p8_latest, on="URN", how="left")

    # School info — drop any conflicting cols from df first to avoid _x/_y suffixes
    school_info = schools[["URN", "SCHNAME", "LANAME", "LA", "SCHOOLTYPE",
                            "MINORGROUP", "GENDER", "ADMPOL", "RELCHAR", "POSTCODE"]].drop_duplicates("URN")
    df = df.drop(columns=[c for c in school_info.columns if c in df.columns and c != "URN"], errors="ignore")
    df = df.merge(school_info, on="URN", how="left")

    # Census context
    df = df.merge(census_prep, on="URN", how="left")

    # Absence
    df = df.merge(abs_prep, on="URN", how="left")

    # Trends
    df = df.merge(trends_df, on="URN", how="left")

    # Destinations (latest year)
    DEST_COLS = ["EDUCATIONPER", "SCH_6THPER", "SIXTH_COLPER",
                 "EMPLOYMENTPER", "APPRENPER", "NOT_SUSTAINEDPER", "UNKNOWNPER"]
    ks4dest = to_num(ks4dest, DEST_COLS)
    dest_latest = latest_year_per_school(ks4dest, DEST_COLS, id_col="URN")
    dest_latest["pct_any_sixthform"] = dest_latest["SCH_6THPER"].fillna(0) + dest_latest["SIXTH_COLPER"].fillna(0)
    dest_latest = dest_latest.rename(columns={
        "EDUCATIONPER":     "dest_pct_education",
        "EMPLOYMENTPER":    "dest_pct_employment",
        "APPRENPER":        "dest_pct_apprentice",
        "NOT_SUSTAINEDPER": "dest_pct_neet",
        "UNKNOWNPER":       "dest_pct_unknown",
        "pct_any_sixthform":"dest_pct_sixthform",
    })[["URN", "dest_pct_education", "dest_pct_sixthform",
        "dest_pct_employment", "dest_pct_apprentice",
        "dest_pct_neet", "dest_pct_unknown"]]
    df = df.merge(dest_latest, on="URN", how="left")

    # ── Derived flags ─────────────────────────────────────────────────────────
    p8_median = df["P8MEA"].median()
    att8_median = df["ATT8SCR"].median()
    df["punching_above_weight"] = (
        (df["P8MEA"] > p8_median) & (df["ATT8SCR"] < att8_median)
    ).astype("Int8")

    # ── Composite score (0–100) ───────────────────────────────────────────────
    # Components: P8 (35%), basics5 (25%), ebacc_entry (10%),
    #             absence penalty (15%), destinations education (15%)
    df["_r_p8"]      = pct_rank_0_100(df["P8MEA"])
    df["_r_basics5"] = pct_rank_0_100(df["PTL2BASICS_95"])
    df["_r_ebacc"]   = pct_rank_0_100(df["PTEBACC_94"])
    df["_r_absence"] = pct_rank_inverted(df["absence_pct"])
    df["_r_dest"]    = pct_rank_0_100(df["dest_pct_education"])

    # fillna(50) treats missing components as London-median — neutral, not penalising
    weights = {"_r_p8": 0.35, "_r_basics5": 0.25, "_r_ebacc": 0.10,
               "_r_absence": 0.15, "_r_dest": 0.15}
    df["composite_score"] = sum(df[c].fillna(50) * w for c, w in weights.items())
    df["composite_score"] = df["composite_score"].round(1)
    df = df.drop(columns=[c for c in df.columns if c.startswith("_r_")])

    # ── Rename for clarity ────────────────────────────────────────────────────
    df = df.rename(columns={
        "ATT8SCR":              "attainment8",
        "P8MEA":                "progress8",
        "P8CILOW":              "progress8_ci_low",
        "P8CIUPP":              "progress8_ci_high",
        "PTL2BASICS_94":        "pct_grade4_eng_maths",
        "PTL2BASICS_95":        "pct_grade5_eng_maths",
        "PTEBACC_94":           "pct_ebacc_4plus",
        "PTEBACC_95":           "pct_ebacc_5plus",
        "TPUP":                 "ks4_cohort",
        "ATT8SCR_FSM6CLA1A":    "attainment8_fsm",
        "ATT8SCR_NFSM6CLA1A":   "attainment8_nonfsm",
        "DIFFN_ATT8":           "fsm_gap_att8",
        "P8MEA_FSM6CLA1A":      "progress8_fsm",
        "P8MEA_NFSM6CLA1A":     "progress8_nonfsm",
        "DIFFN_P8MEA":          "fsm_gap_progress8",
        "NFTYPE":               "school_type_dfe",
        "EGENDER":              "admissions_gender",
        "academic_year":        "data_year",
    })

    keep_cols = [
        "URN", "SCHNAME", "LANAME", "LA", "POSTCODE",
        "SCHOOLTYPE", "MINORGROUP", "school_type_dfe", "admissions_gender",
        "GENDER", "ADMPOL", "RELCHAR", "data_year",
        "ks4_cohort", "census_total_pupils", "pct_fsm", "pct_eal", "pct_sen_support", "pct_sen_ehcp",
        "attainment8", "progress8", "progress8_ci_low", "progress8_ci_high",
        "pct_grade4_eng_maths", "pct_grade5_eng_maths",
        "pct_ebacc_4plus", "pct_ebacc_5plus",
        "attainment8_fsm", "attainment8_nonfsm", "fsm_gap_att8",
        "progress8_fsm", "progress8_nonfsm", "fsm_gap_progress8",
        "absence_pct", "persistent_absence_pct", "absence_year",
        "dest_pct_education", "dest_pct_sixthform", "dest_pct_employment",
        "dest_pct_apprentice", "dest_pct_neet", "dest_pct_unknown",
        "p8_trend", "att8_trend", "basics5_trend", "trend_from_year", "trend_to_year",
        "punching_above_weight", "composite_score",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]
    save(conn, df, "metrics_ks4")
    return df


# ── KS2 metrics ───────────────────────────────────────────────────────────────

def build_ks2(ks2, schools, census_prep, abs_prep, conn):
    print("\nBuilding KS2 metrics...")

    # READPROG_23/WRITPROG_23/MATPROG_23 = current year progress in 2023-24 and 2024-25 files
    # (DfE renamed them with year suffix; stored as strings in the model table)
    METRICS = ["PTRWM_EXP", "PTRWM_HIGH", "PTREAD_EXP", "PTMAT_EXP",
               "READ_AVERAGE", "MAT_AVERAGE", "GPS_AVERAGE",
               "READPROG_23", "WRITPROG_23", "MATPROG_23",
               "PTRWM_EXP_FSM6CLA1A", "PTRWM_EXP_NotFSM6CLA1A", "DIFFN_RWM_EXP",
               "TOTPUPS"]

    ks2 = to_num(ks2, METRICS)

    # ── Trend ─────────────────────────────────────────────────────────────────
    ks2_sorted = ks2.sort_values(["URN", "academic_year"])
    trends = []
    for urn, grp in ks2_sorted.groupby("URN"):
        grp = grp.dropna(subset=["PTRWM_EXP"])
        if len(grp) >= 2:
            first, last = grp.iloc[0], grp.iloc[-1]
            trends.append({
                "URN": urn,
                "rwm_trend":       round(last["PTRWM_EXP"] - first["PTRWM_EXP"], 2),
                "read_prog_trend": round(last["READPROG_23"] - first["READPROG_23"], 3)
                                   if pd.notna(last["READPROG_23"]) and pd.notna(first["READPROG_23"]) else np.nan,
                "trend_from_year": first["academic_year"],
                "trend_to_year":   last["academic_year"],
            })
    trends_df = pd.DataFrame(trends) if trends else pd.DataFrame(
        columns=["URN", "rwm_trend", "read_prog_trend", "trend_from_year", "trend_to_year"])

    # ── Latest year ───────────────────────────────────────────────────────────
    df = latest_year_per_school(ks2, METRICS, id_col="URN")

    # Average progress score across subjects
    df["avg_progress"] = df[["READPROG_23", "WRITPROG_23", "MATPROG_23"]].mean(axis=1).round(3)

    school_info = schools[["URN", "SCHNAME", "LANAME", "LA", "SCHOOLTYPE",
                            "MINORGROUP", "GENDER", "ADMPOL", "RELCHAR", "POSTCODE"]].drop_duplicates("URN")
    df = df.drop(columns=[c for c in school_info.columns if c in df.columns and c != "URN"], errors="ignore")
    df = df.merge(school_info, on="URN", how="left")
    df = df.merge(census_prep, on="URN", how="left")
    df = df.merge(abs_prep, on="URN", how="left")
    df = df.merge(trends_df, on="URN", how="left")

    # ── Composite score ───────────────────────────────────────────────────────
    # Components: RWM expected (30%), avg progress (40%), absence (15%), RWM high (15%)
    df["_r_rwm"]     = pct_rank_0_100(df["PTRWM_EXP"])
    df["_r_prog"]    = pct_rank_0_100(df["avg_progress"])
    df["_r_absence"] = pct_rank_inverted(df["absence_pct"])
    df["_r_high"]    = pct_rank_0_100(df["PTRWM_HIGH"])

    # fillna(50) treats missing components as London-median — neutral, not penalising
    weights = {"_r_rwm": 0.30, "_r_prog": 0.40, "_r_absence": 0.15, "_r_high": 0.15}
    df["composite_score"] = sum(df[c].fillna(50) * w for c, w in weights.items())
    df["composite_score"] = df["composite_score"].round(1)
    df = df.drop(columns=[c for c in df.columns if c.startswith("_r_")])

    df = df.rename(columns={
        "PTRWM_EXP":               "pct_rwm_expected",
        "PTRWM_HIGH":              "pct_rwm_high",
        "PTREAD_EXP":              "pct_reading_expected",
        "PTMAT_EXP":               "pct_maths_expected",
        "READ_AVERAGE":            "reading_avg_score",
        "MAT_AVERAGE":             "maths_avg_score",
        "GPS_AVERAGE":             "gps_avg_score",
        "READPROG_23":             "reading_progress",
        "WRITPROG_23":             "writing_progress",
        "MATPROG_23":              "maths_progress",
        "PTRWM_EXP_FSM6CLA1A":    "pct_rwm_expected_fsm",
        "PTRWM_EXP_NotFSM6CLA1A": "pct_rwm_expected_nonfsm",
        "DIFFN_RWM_EXP":          "fsm_gap_rwm",
        "TOTPUPS":                 "total_pupils",
        "academic_year":           "data_year",
    })

    keep_cols = [
        "URN", "SCHNAME", "LANAME", "LA", "POSTCODE",
        "SCHOOLTYPE", "MINORGROUP", "GENDER", "ADMPOL", "RELCHAR", "data_year",
        "total_pupils", "census_total_pupils", "pct_fsm", "pct_eal", "pct_sen_support", "pct_sen_ehcp",
        "pct_rwm_expected", "pct_rwm_high", "pct_reading_expected", "pct_maths_expected",
        "reading_avg_score", "maths_avg_score", "gps_avg_score",
        "reading_progress", "writing_progress", "maths_progress", "avg_progress",

        "pct_rwm_expected_fsm", "pct_rwm_expected_nonfsm", "fsm_gap_rwm",
        "absence_pct", "persistent_absence_pct", "absence_year",
        "rwm_trend", "read_prog_trend", "trend_from_year", "trend_to_year",
        "composite_score",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]
    save(conn, df, "metrics_ks2")
    return df


# ── KS5 metrics ───────────────────────────────────────────────────────────────

def build_ks5(ks5, schools, census_prep, abs_prep, ks5dest, conn):
    print("\nBuilding KS5 metrics...")

    METRICS = ["VA_INS_ALEV", "UCI_INS_ALEV", "LCI_INS_ALEV",
               "PTAAB_2FAC", "TALLPUP_ALEV_1618", "TPUP1618"]

    ks5 = to_num(ks5, METRICS)

    # ── Trend ─────────────────────────────────────────────────────────────────
    ks5_sorted = ks5.sort_values(["URN", "academic_year"])
    trends = []
    for urn, grp in ks5_sorted.groupby("URN"):
        grp = grp.dropna(subset=["VA_INS_ALEV"])
        if len(grp) >= 2:
            first, last = grp.iloc[0], grp.iloc[-1]
            trends.append({
                "URN": urn,
                "va_trend":        round(last["VA_INS_ALEV"] - first["VA_INS_ALEV"], 3),
                "trend_from_year": first["academic_year"],
                "trend_to_year":   last["academic_year"],
            })
    trends_df = pd.DataFrame(trends) if trends else pd.DataFrame(
        columns=["URN", "va_trend", "trend_from_year", "trend_to_year"])

    df = latest_year_per_school(ks5, METRICS, id_col="URN")

    school_info = schools[["URN", "SCHNAME", "LANAME", "LA", "SCHOOLTYPE",
                            "MINORGROUP", "GENDER", "ADMPOL", "RELCHAR", "POSTCODE"]].drop_duplicates("URN")
    df = df.drop(columns=[c for c in school_info.columns if c in df.columns and c != "URN"], errors="ignore")
    df = df.merge(school_info, on="URN", how="left")
    df = df.merge(census_prep, on="URN", how="left")
    df = df.merge(abs_prep, on="URN", how="left")
    df = df.merge(trends_df, on="URN", how="left")

    # Destinations
    DEST_COLS = ["TOT_HEPER", "TOT_EDUCATIONPER", "TOT_EMPLOYMENTPER", "TOT_NOT_SUSTAINEDPER"]
    ks5dest = to_num(ks5dest, DEST_COLS)
    dest_latest = latest_year_per_school(ks5dest, DEST_COLS, id_col="URN")
    dest_latest = dest_latest.rename(columns={
        "TOT_HEPER":             "dest_pct_he",
        "TOT_EDUCATIONPER":      "dest_pct_education",
        "TOT_EMPLOYMENTPER":     "dest_pct_employment",
        "TOT_NOT_SUSTAINEDPER":  "dest_pct_neet",
    })[["URN", "dest_pct_he", "dest_pct_education", "dest_pct_employment", "dest_pct_neet"]]
    df = df.merge(dest_latest, on="URN", how="left")

    # ── Composite score ───────────────────────────────────────────────────────
    # Components: VA (40%), AAB facilitating (25%), HE destinations (25%), absence (10%)
    df["_r_va"]      = pct_rank_0_100(df["VA_INS_ALEV"])
    df["_r_aab"]     = pct_rank_0_100(df["PTAAB_2FAC"])
    df["_r_he"]      = pct_rank_0_100(df["dest_pct_he"])
    df["_r_absence"] = pct_rank_inverted(df["absence_pct"])

    # fillna(50) treats missing components as London-median — neutral, not penalising
    weights = {"_r_va": 0.40, "_r_aab": 0.25, "_r_he": 0.25, "_r_absence": 0.10}
    df["composite_score"] = sum(df[c].fillna(50) * w for c, w in weights.items())
    df["composite_score"] = df["composite_score"].round(1)
    df = df.drop(columns=[c for c in df.columns if c.startswith("_r_")])

    df = df.rename(columns={
        "VA_INS_ALEV":        "alevel_value_added",
        "UCI_INS_ALEV":       "va_ci_high",
        "LCI_INS_ALEV":       "va_ci_low",
        "PTAAB_2FAC":         "pct_aab_facilitating",
        "TALLPUP_ALEV_1618":  "alevel_cohort",
        "TPUP1618":           "total_1618_pupils",
        "NFTYPE/FESITYPE":    "provider_type",
        "academic_year":      "data_year",
    })

    keep_cols = [
        "URN", "SCHNAME", "LANAME", "LA", "POSTCODE",
        "SCHOOLTYPE", "MINORGROUP", "provider_type", "GENDER", "ADMPOL", "RELCHAR", "data_year",
        "alevel_cohort", "total_1618_pupils", "census_total_pupils",
        "pct_fsm", "pct_eal", "pct_sen_support", "pct_sen_ehcp",
        "alevel_value_added", "va_ci_low", "va_ci_high",
        "pct_aab_facilitating",
        "dest_pct_he", "dest_pct_education", "dest_pct_employment", "dest_pct_neet",
        "absence_pct", "persistent_absence_pct", "absence_year",
        "va_trend", "trend_from_year", "trend_to_year",
        "composite_score",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]
    save(conn, df, "metrics_ks5")
    return df


# ── Borough-level aggregates ──────────────────────────────────────────────────

def build_la_summary(ks4_df, ks2_df, ks5_df, conn):
    print("\nBuilding borough summary...")

    rows = []

    def r(val, n): return round(val, n) if pd.notna(val) else np.nan

    # KS4 by borough
    for la, grp in ks4_df.groupby("LANAME"):
        rows.append({
            "borough": la, "phase": "KS4",
            "n_schools": len(grp),
            "avg_progress8":            r(grp["progress8"].mean(), 3),
            "avg_attainment8":          r(grp["attainment8"].mean(), 1),
            "avg_pct_grade5_eng_maths": r(grp["pct_grade5_eng_maths"].mean(), 1),
            "avg_pct_ebacc":            r(grp["pct_ebacc_4plus"].mean(), 1),
            "avg_absence_pct":          r(grp["absence_pct"].mean(), 2),
            "avg_composite":            r(grp["composite_score"].mean(), 1),
            "avg_fsm_gap_p8":           r(grp["fsm_gap_progress8"].mean(), 3),
        })

    # KS2 by borough
    for la, grp in ks2_df.groupby("LANAME"):
        rows.append({
            "borough": la, "phase": "KS2",
            "n_schools": len(grp),
            "avg_pct_rwm_expected": r(grp["pct_rwm_expected"].mean(), 1),
            "avg_pct_rwm_high":     r(grp["pct_rwm_high"].mean(), 1),
            "avg_progress":         r(grp["avg_progress"].mean(), 3),
            "avg_absence_pct":      r(grp["absence_pct"].mean(), 2),
            "avg_composite":        r(grp["composite_score"].mean(), 1),
            "avg_fsm_gap_rwm":      r(grp["fsm_gap_rwm"].mean(), 1),
        })

    # KS5 by borough
    for la, grp in ks5_df.groupby("LANAME"):
        rows.append({
            "borough": la, "phase": "KS5",
            "n_schools": len(grp),
            "avg_va_alevel":   r(grp["alevel_value_added"].mean(), 3),
            "avg_pct_aab":     r(grp["pct_aab_facilitating"].mean(), 1),
            "avg_pct_he":      r(grp["dest_pct_he"].mean(), 1),
            "avg_absence_pct": r(grp["absence_pct"].mean(), 2),
            "avg_composite":   r(grp["composite_score"].mean(), 1),
        })

    df = pd.DataFrame(rows)
    save(conn, df, "metrics_la")
    return df


# ── School type aggregates ────────────────────────────────────────────────────

def build_type_summary(ks4_df, ks2_df, ks5_df, conn):
    print("\nBuilding school type summary...")

    rows = []

    for phase, df, metrics in [
        ("KS4", ks4_df, {
            "avg_progress8":            ("progress8", "mean"),
            "avg_attainment8":          ("attainment8", "mean"),
            "avg_pct_grade5_eng_maths": ("pct_grade5_eng_maths", "mean"),
            "avg_pct_ebacc":            ("pct_ebacc_4plus", "mean"),
            "avg_fsm_gap_p8":           ("fsm_gap_progress8", "mean"),
            "avg_composite":            ("composite_score", "mean"),
        }),
        ("KS2", ks2_df, {
            "avg_pct_rwm_expected": ("pct_rwm_expected", "mean"),
            "avg_pct_rwm_high":     ("pct_rwm_high", "mean"),
            "avg_progress":         ("avg_progress", "mean"),
            "avg_fsm_gap_rwm":      ("fsm_gap_rwm", "mean"),
            "avg_composite":        ("composite_score", "mean"),
        }),
        ("KS5", ks5_df, {
            "avg_va_alevel": ("alevel_value_added", "mean"),
            "avg_pct_aab":   ("pct_aab_facilitating", "mean"),
            "avg_pct_he":    ("dest_pct_he", "mean"),
            "avg_composite": ("composite_score", "mean"),
        }),
    ]:
        for stype, grp in df.groupby("MINORGROUP"):
            row = {"phase": phase, "school_type": stype, "n_schools": len(grp)}
            for out_col, (src_col, func) in metrics.items():
                if src_col in grp.columns:
                    row[out_col] = round(getattr(grp[src_col], func)(), 3)
            rows.append(row)

    df_out = pd.DataFrame(rows)
    save(conn, df_out, "metrics_type")
    return df_out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading from: {DB_PATH}")
    conn = get_conn()

    try:
        schools, ks4, ks2, ks5, census, absences, ks4dest, ks5dest = load_tables(conn)

        census_prep = prep_census(census)
        abs_prep    = prep_absences(absences)

        ks4_df = build_ks4(ks4, schools, census_prep, abs_prep, ks4dest, conn)
        ks2_df = build_ks2(ks2, schools, census_prep, abs_prep, conn)
        ks5_df = build_ks5(ks5, schools, census_prep, abs_prep, ks5dest, conn)

        build_la_summary(ks4_df, ks2_df, ks5_df, conn)
        build_type_summary(ks4_df, ks2_df, ks5_df, conn)

        conn.commit()

        print("\n=== Done ===")
        print("Tables written:")
        for t in ["metrics_ks4", "metrics_ks2", "metrics_ks5", "metrics_la", "metrics_type"]:
            n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {t}", conn).iloc[0, 0]
            print(f"  {t}: {n:,} rows")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
