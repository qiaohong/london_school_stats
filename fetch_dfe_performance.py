"""
DfE School Performance Data Collector
Fetches KS2 (Primary) and KS4 (Secondary) attainment data from
Explore Education Statistics and loads it into the existing SQLite database.

Run fetch_ofsted_data.py first to populate the schools table.
"""

import requests
import pandas as pd
import sqlite3
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "ofsted_schools.db"
DATA_DIR = Path(__file__).parent / "data"

# DfE Explore Education Statistics — school-level CSV downloads
# KS2: 2024/25 revised institution-level data (Primary)
KS2_URL = (
    "https://explore-education-statistics.service.gov.uk"
    "/data-catalogue/data-set/b361b4c3-21b9-46fd-9126-b8060c6a40e2/csv"
)
KS2_FILENAME = "ks2_institution_level_2024_25.csv"

# KS4: 2023/24 final institution-level performance (Secondary)
# 2023/24 is the most recent year with Progress 8 (2024/25 cohort lacks KS2 prior attainment due to COVID)
KS4_URL = (
    "https://explore-education-statistics.service.gov.uk"
    "/data-catalogue/data-set/c8f753ef-b76f-41a3-8949-13382e131054/csv"
)
KS4_FILENAME = "ks4_institution_level_2023_24.csv"


# ── Download helper ───────────────────────────────────────────────────────────

def download(url, filename):
    DATA_DIR.mkdir(exist_ok=True)
    filepath = DATA_DIR / filename

    if filepath.exists():
        print(f"Already downloaded: {filename} — skipping.")
    else:
        print(f"Downloading {filename}  (this may take a minute)...")
        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        filepath.write_bytes(resp.content)
        print(f"Saved to {filepath}")

    return filepath


# ── KS2 processing ───────────────────────────────────────────────────────────

def process_ks2(filepath):
    """
    The KS2 file has multiple rows per school — one row per subject × breakdown.
    We pivot to get one row per school with reading/writing/maths side by side.

    Key columns we extract:
      school_urn, breakdown_topic, breakdown, subject,
      expected_standard_pupil_percent, higher_standard_pupil_percent,
      average_scaled_score, progress_measure_score,
      t_disadvantaged, pt_disadvantaged
    """
    print("Processing KS2 data...")
    df = pd.read_csv(filepath, low_memory=False)

    print(f"  Raw rows: {len(df)}")

    # Keep only school-level rows for all pupils combined
    df = df[
        (df["geographic_level"].str.lower() == "school")
        & (df["breakdown"].str.lower().isin(["all pupils", "total"]))
    ].copy()

    print(f"  After filtering for school-level / all pupils: {len(df)}")

    # Normalise subject names
    df["subject"] = df["subject"].str.strip().str.lower()

    # Subjects we want
    subjects = ["reading", "writing", "maths"]
    df = df[df["subject"].isin(subjects)]

    def to_num(series):
        return pd.to_numeric(series, errors="coerce")

    # Pivot: one row per school, columns per subject
    records = {}
    for urn, group in df.groupby("school_urn"):
        rec = {"urn": int(urn)}

        for _, row in group.iterrows():
            subj = row["subject"]
            rec[f"{subj}_pct_expected"]  = to_num(pd.Series([row.get("expected_standard_pupil_percent")])).iloc[0]
            rec[f"{subj}_pct_higher"]    = to_num(pd.Series([row.get("higher_standard_pupil_percent")])).iloc[0]
            rec[f"{subj}_avg_score"]     = to_num(pd.Series([row.get("average_scaled_score")])).iloc[0]
            rec[f"{subj}_progress"]      = to_num(pd.Series([row.get("progress_measure_score")])).iloc[0]

        # Disadvantaged / FSM proxy — same across subjects, take from any row
        first = group.iloc[0]
        rec["pct_disadvantaged"] = to_num(pd.Series([first.get("pt_disadvantaged")])).iloc[0]
        rec["academic_year"] = str(first.get("time_period", "")).strip()

        records[urn] = rec

    result = pd.DataFrame(list(records.values()))
    print(f"  Schools after pivot: {len(result)}")
    return result


# ── KS4 processing ───────────────────────────────────────────────────────────

def process_ks4(filepath):
    """
    The KS4 file has multiple rows per school broken down by pupil characteristics.
    We extract the 'All pupils' row per school for headline measures.

    Key columns:
      school_urn, avg_att8, avg_p8score, avg_ebaccaps,
      pt_l2basics_94 (% grade 4+ English & maths),
      pt_anypass, pt_disadvantaged
    """
    print("Processing KS4 data...")
    df = pd.read_csv(filepath, low_memory=False)

    print(f"  Raw rows: {len(df)}")

    # Keep school-level, all-pupils rows
    df = df[
        (df["geographic_level"].str.lower() == "school")
        & (df["breakdown"].str.strip().str.lower().isin(["all pupils", "total"]))
    ].copy()

    print(f"  After filtering for school-level / all pupils: {len(df)}")

    def to_num(series):
        return pd.to_numeric(series, errors="coerce")

    result = pd.DataFrame({
        "urn":                  df["school_urn"].astype(int),
        "academic_year":        df["time_period"].astype(str).str.strip(),
        "avg_attainment8":      to_num(df.get("avg_att8")),
        "avg_progress8":        to_num(df.get("avg_p8score")),
        "avg_ebacc_aps":        to_num(df.get("avg_ebaccaps")),
        "pct_grade4_eng_maths": to_num(df.get("pt_l2basics_94")),   # % achieving grade 4+ in both
        "pct_grade5_eng_maths": to_num(df.get("pt_l2basics_95")),   # % achieving grade 5+ in both
        "pct_disadvantaged":    to_num(df.get("pt_disadvantaged")),
    }).drop_duplicates(subset="urn")

    print(f"  Schools after dedup: {len(result)}")
    return result


# ── Save to SQLite ────────────────────────────────────────────────────────────

def save_to_sqlite(ks2_df, ks4_df):
    print(f"Saving to SQLite: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS primary_performance (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                urn             INTEGER NOT NULL REFERENCES schools(urn),
                academic_year   TEXT,

                -- Reading (KS2)
                reading_pct_expected    REAL,   -- % meeting expected standard
                reading_pct_higher      REAL,   -- % achieving higher standard
                reading_avg_score       REAL,   -- average scaled score
                reading_progress        REAL,   -- progress score vs national avg

                -- Writing (teacher assessed)
                writing_pct_expected    REAL,
                writing_pct_higher      REAL,
                writing_avg_score       REAL,
                writing_progress        REAL,

                -- Maths (KS2)
                maths_pct_expected      REAL,
                maths_pct_higher        REAL,
                maths_avg_score         REAL,
                maths_progress          REAL,

                -- Pupil characteristics
                pct_disadvantaged       REAL,   -- % FSM-eligible / disadvantaged pupils

                UNIQUE(urn, academic_year)
            );

            CREATE TABLE IF NOT EXISTS secondary_performance (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                urn                     INTEGER NOT NULL REFERENCES schools(urn),
                academic_year           TEXT,

                avg_attainment8         REAL,   -- average Attainment 8 score
                avg_progress8           REAL,   -- average Progress 8 score (not available 2024/25)
                avg_ebacc_aps           REAL,   -- average EBacc Academic Performance Score
                pct_grade4_eng_maths    REAL,   -- % achieving grade 4+ in English AND maths
                pct_grade5_eng_maths    REAL,   -- % achieving grade 5+ in English AND maths

                -- Pupil characteristics
                pct_disadvantaged       REAL,   -- % FSM-eligible / disadvantaged pupils

                UNIQUE(urn, academic_year)
            );
        """)

        # Get valid URNs from schools table (London/Surrey only)
        valid_urns = {row[0] for row in cursor.execute("SELECT urn FROM schools").fetchall()}
        ks2_df = ks2_df[ks2_df["urn"].isin(valid_urns)]
        ks4_df = ks4_df[ks4_df["urn"].isin(valid_urns)]
        print(f"  KS2 schools matched to our schools table: {len(ks2_df)}")
        print(f"  KS4 schools matched to our schools table: {len(ks4_df)}")

        # Insert KS2
        ks2_rows = []
        for _, row in ks2_df.iterrows():
            ks2_rows.append((
                int(row["urn"]),
                row.get("academic_year"),
                row.get("reading_pct_expected"),
                row.get("reading_pct_higher"),
                row.get("reading_avg_score"),
                row.get("reading_progress"),
                row.get("writing_pct_expected"),
                row.get("writing_pct_higher"),
                row.get("writing_avg_score"),
                row.get("writing_progress"),
                row.get("maths_pct_expected"),
                row.get("maths_pct_higher"),
                row.get("maths_avg_score"),
                row.get("maths_progress"),
                row.get("pct_disadvantaged"),
            ))

        cursor.executemany("""
            INSERT INTO primary_performance (
                urn, academic_year,
                reading_pct_expected, reading_pct_higher, reading_avg_score, reading_progress,
                writing_pct_expected, writing_pct_higher, writing_avg_score, writing_progress,
                maths_pct_expected, maths_pct_higher, maths_avg_score, maths_progress,
                pct_disadvantaged
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(urn, academic_year) DO UPDATE SET
                reading_pct_expected=excluded.reading_pct_expected,
                reading_pct_higher=excluded.reading_pct_higher,
                maths_pct_expected=excluded.maths_pct_expected,
                maths_pct_higher=excluded.maths_pct_higher,
                writing_pct_expected=excluded.writing_pct_expected,
                pct_disadvantaged=excluded.pct_disadvantaged
        """, ks2_rows)

        # Insert KS4
        ks4_rows = []
        for _, row in ks4_df.iterrows():
            ks4_rows.append((
                int(row["urn"]),
                row.get("academic_year"),
                row.get("avg_attainment8"),
                row.get("avg_progress8"),
                row.get("avg_ebacc_aps"),
                row.get("pct_grade4_eng_maths"),
                row.get("pct_grade5_eng_maths"),
                row.get("pct_disadvantaged"),
            ))

        cursor.executemany("""
            INSERT INTO secondary_performance (
                urn, academic_year,
                avg_attainment8, avg_progress8, avg_ebacc_aps,
                pct_grade4_eng_maths, pct_grade5_eng_maths,
                pct_disadvantaged
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(urn, academic_year) DO UPDATE SET
                avg_attainment8=excluded.avg_attainment8,
                avg_progress8=excluded.avg_progress8,
                avg_ebacc_aps=excluded.avg_ebacc_aps,
                pct_grade4_eng_maths=excluded.pct_grade4_eng_maths,
                pct_grade5_eng_maths=excluded.pct_grade5_eng_maths,
                pct_disadvantaged=excluded.pct_disadvantaged
        """, ks4_rows)

        conn.commit()

    print(f"Done. Primary schools inserted/updated:   {len(ks2_rows)}")
    print(f"      Secondary schools inserted/updated: {len(ks4_rows)}")
    print(f"      Database: {DB_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ks2_file = download(KS2_URL, KS2_FILENAME)
    ks4_file = download(KS4_URL, KS4_FILENAME)

    ks2_df = process_ks2(ks2_file)
    ks4_df = process_ks4(ks4_file)

    save_to_sqlite(ks2_df, ks4_df)
