"""
Supplementary School Data Collector
Fetches and loads three additional datasets into the existing SQLite database:
  1. Pupil absence (school level, 2023/24)
  2. Suspensions and permanent exclusions (school level, 2023/24)
  3. School applications and offers (school level, 2024/25) — pre-downloaded

Run fetch_ofsted_data.py first to populate the schools table.

Note on KS4 destinations: DfE does not publish school-level destination data
as a bulk download. Only national and LA-level data is publicly available.
"""

import requests
import pandas as pd
import sqlite3
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH   = Path(__file__).parent / "ofsted_schools.db"
DATA_DIR  = Path(__file__).parent / "data"

TARGET_REGIONS            = ["London"]
TARGET_AUTHORITIES_PATTERN = r"Surrey"
TARGET_PHASES             = ["Primary", "Secondary"]

# Dataset download URLs
ABSENCE_URL      = (
    "https://explore-education-statistics.service.gov.uk"
    "/data-catalogue/data-set/1ef1689a-070a-4e0b-9314-512db23a3cc9/csv"
)
ABSENCE_FILENAME = "absence_school_level_2023_24.csv"

EXCLUSIONS_URL      = (
    "https://explore-education-statistics.service.gov.uk"
    "/data-catalogue/data-set/6ffc5087-5f61-47a1-9086-d1c374039d1b/csv"
)
EXCLUSIONS_FILENAME = "exclusions_school_level_2023_24.csv"

# Already downloaded manually
APPLICATIONS_FILENAME = "AppsandOffers_2024_SchoolLevel.csv"


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


# ── Filter helper ─────────────────────────────────────────────────────────────

def filter_london_surrey(df, region_col, la_col, phase_col):
    london_mask = df[region_col].str.strip().isin(TARGET_REGIONS)
    surrey_mask = df[la_col].str.contains(TARGET_AUTHORITIES_PATTERN, case=False, na=False)
    # Normalise phase: "State-funded primary" → "Primary", "State-funded secondary" → "Secondary"
    phase_norm = df[phase_col].str.replace(r"(?i)state-funded\s+", "", regex=True).str.strip().str.title()
    phase_mask  = phase_norm.isin(TARGET_PHASES)
    return df[(london_mask | surrey_mask) & phase_mask].copy()


# ── 1. Absence ────────────────────────────────────────────────────────────────

def process_absence(filepath):
    print("Processing absence data...")
    df = pd.read_csv(filepath, low_memory=False, encoding="utf-8-sig")
    print(f"  Raw rows: {len(df)}")

    # Keep most recent full academic year only
    latest_year = df["time_period"].max()
    df = df[df["time_period"] == latest_year]
    print(f"  Using year: {latest_year}  rows: {len(df)}")

    df = filter_london_surrey(df, "region_name", "la_name", "education_phase")
    print(f"  After London/Surrey filter: {len(df)}")

    def to_num(col):
        return pd.to_numeric(df.get(col), errors="coerce")

    # Build rates — dataset has both count columns and percent columns
    # Percent columns end in _percent or _rate; fall back to calculating from counts
    def rate_col(pct_name, num_name, denom_name):
        if pct_name in df.columns:
            return to_num(pct_name)
        num   = to_num(num_name)
        denom = to_num(denom_name)
        return (num / denom * 100).where(denom > 0)

    result = pd.DataFrame({
        "urn":                      pd.to_numeric(df["school_urn"], errors="coerce"),
        "academic_year":            df["time_period"].astype(str),
        "overall_absence_rate":     rate_col("sess_overall_percent",
                                             "sess_overall", "sess_possible"),
        "authorised_absence_rate":  rate_col("sess_authorised_percent",
                                             "sess_authorised", "sess_possible"),
        "unauthorised_absence_rate":rate_col("sess_unauthorised_percent",
                                             "sess_unauthorised", "sess_possible"),
        "persistent_absence_rate":  rate_col("enrolments_pa_10_percent",
                                             "enrolments_pa_10_exact", "enrolments"),
    }).dropna(subset=["urn"])

    result["urn"] = result["urn"].astype(int)
    print(f"  Schools processed: {len(result)}")
    return result


# ── 2. Exclusions ─────────────────────────────────────────────────────────────

def process_exclusions(filepath):
    print("Processing exclusions/suspensions data...")
    df = pd.read_csv(filepath, low_memory=False, encoding="utf-8-sig")
    print(f"  Raw rows: {len(df)}")

    latest_year = df["time_period"].max()
    df = df[df["time_period"] == latest_year]
    print(f"  Using year: {latest_year}  rows: {len(df)}")

    df = filter_london_surrey(df, "region_name", "la_name", "education_phase")
    print(f"  After London/Surrey filter: {len(df)}")

    def to_num(col):
        return pd.to_numeric(df.get(col), errors="coerce")

    result = pd.DataFrame({
        "urn":                   pd.to_numeric(df["school_urn"], errors="coerce"),
        "academic_year":         df["time_period"].astype(str),
        "headcount":             to_num("headcount"),
        "perm_excl_count":       to_num("perm_excl"),
        "perm_excl_rate":        to_num("perm_excl_rate"),      # per 1,000 pupils
        "suspension_count":      to_num("suspension"),
        "suspension_rate":       to_num("susp_rate"),           # per 1,000 pupils
        "pct_one_plus_suspension": to_num("one_plus_susp_rate"), # % pupils with ≥1 suspension
    }).dropna(subset=["urn"])

    result["urn"] = result["urn"].astype(int)
    print(f"  Schools processed: {len(result)}")
    return result


# ── 3. Applications and offers ────────────────────────────────────────────────

def process_applications(filepath):
    print("Processing applications and offers data...")
    df = pd.read_csv(filepath, low_memory=False, encoding="utf-8-sig")
    print(f"  Raw rows: {len(df)}")

    # Map phase names to match our schools table
    df["education_phase"] = df["school_phase"].str.strip().str.title()

    df = filter_london_surrey(df, "region_name", "la_name", "education_phase")
    print(f"  After London/Surrey filter: {len(df)}")

    def to_num(col):
        return pd.to_numeric(df.get(col), errors="coerce")

    result = pd.DataFrame({
        "urn":                          pd.to_numeric(df["school_urn"], errors="coerce"),
        "time_period":                  df["time_period"].astype(str),
        "entry_year":                   df["entry_year"].astype(str).str.strip(),  # R=Reception, 7=Yr7
        "places_offered":               to_num("total_number_places_offered"),
        "times_put_as_1st_preference":  to_num("times_put_as_1st_preference"),
        "times_put_as_any_preference":  to_num("times_put_as_any_preferred_school"),
        "first_preference_offers":      to_num("number_1st_preference_offers"),
        "preferred_offers":             to_num("number_preferred_offers"),
        # Oversubscription: 1st pref applications per place (>1 means oversubscribed)
        "oversubscription_ratio":       to_num("proportion_1stprefs_v_totaloffers"),
        "fsm_eligible_pct":             to_num("FSM_eligible_percent"),
        "admissions_policy":            df["admissions_policy"].astype(str).str.strip(),
    }).dropna(subset=["urn"])

    result["urn"] = result["urn"].astype(int)
    print(f"  Schools processed: {len(result)}")
    return result


# ── Save to SQLite ────────────────────────────────────────────────────────────

def save_to_sqlite(absence_df, exclusions_df, applications_df):
    print(f"\nSaving to SQLite: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS absence (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                urn                         INTEGER NOT NULL REFERENCES schools(urn),
                academic_year               TEXT,
                overall_absence_rate        REAL,   -- % of sessions missed overall
                authorised_absence_rate     REAL,   -- % authorised (e.g. illness with note)
                unauthorised_absence_rate   REAL,   -- % unauthorised (e.g. holidays)
                persistent_absence_rate     REAL,   -- % pupils missing 10%+ of sessions
                UNIQUE(urn, academic_year)
            );

            CREATE TABLE IF NOT EXISTS exclusions (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                urn                         INTEGER NOT NULL REFERENCES schools(urn),
                academic_year               TEXT,
                headcount                   INTEGER,
                perm_excl_count             INTEGER,
                perm_excl_rate              REAL,   -- permanent exclusions per 1,000 pupils
                suspension_count            INTEGER,
                suspension_rate             REAL,   -- suspensions per 1,000 pupils
                pct_one_plus_suspension     REAL,   -- % pupils receiving at least one suspension
                UNIQUE(urn, academic_year)
            );

            CREATE TABLE IF NOT EXISTS applications (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                urn                         INTEGER NOT NULL REFERENCES schools(urn),
                time_period                 TEXT,
                entry_year                  TEXT,   -- R=Reception (Primary), 7=Year 7 (Secondary)
                places_offered              INTEGER,
                times_put_as_1st_preference INTEGER, -- how many families chose this school 1st
                times_put_as_any_preference INTEGER,
                first_preference_offers     INTEGER, -- how many 1st choice applicants got a place
                preferred_offers            INTEGER,
                oversubscription_ratio      REAL,   -- 1st pref applications per place (>1 = oversubscribed)
                fsm_eligible_pct            REAL,   -- % pupils eligible for free school meals
                admissions_policy           TEXT,
                UNIQUE(urn, time_period, entry_year)
            );
        """)

        # Filter all three datasets to URNs present in schools table
        valid_urns = {row[0] for row in cursor.execute("SELECT urn FROM schools").fetchall()}
        absence_df      = absence_df[absence_df["urn"].isin(valid_urns)]
        exclusions_df   = exclusions_df[exclusions_df["urn"].isin(valid_urns)]
        applications_df = applications_df[applications_df["urn"].isin(valid_urns)]
        print(f"  Absence matched to our schools table:      {len(absence_df)}")
        print(f"  Exclusions matched to our schools table:   {len(exclusions_df)}")
        print(f"  Applications matched to our schools table: {len(applications_df)}")

        # Insert absence
        absence_rows = [
            (int(r.urn), r.academic_year, r.overall_absence_rate,
             r.authorised_absence_rate, r.unauthorised_absence_rate, r.persistent_absence_rate)
            for r in absence_df.itertuples()
        ]
        cursor.executemany("""
            INSERT INTO absence (urn, academic_year, overall_absence_rate,
                authorised_absence_rate, unauthorised_absence_rate, persistent_absence_rate)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(urn, academic_year) DO UPDATE SET
                overall_absence_rate=excluded.overall_absence_rate,
                authorised_absence_rate=excluded.authorised_absence_rate,
                unauthorised_absence_rate=excluded.unauthorised_absence_rate,
                persistent_absence_rate=excluded.persistent_absence_rate
        """, absence_rows)
        print(f"  Absence rows inserted/updated:      {len(absence_rows)}")

        # Insert exclusions
        excl_rows = [
            (int(r.urn), r.academic_year, r.headcount, r.perm_excl_count,
             r.perm_excl_rate, r.suspension_count, r.suspension_rate, r.pct_one_plus_suspension)
            for r in exclusions_df.itertuples()
        ]
        cursor.executemany("""
            INSERT INTO exclusions (urn, academic_year, headcount, perm_excl_count,
                perm_excl_rate, suspension_count, suspension_rate, pct_one_plus_suspension)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(urn, academic_year) DO UPDATE SET
                perm_excl_rate=excluded.perm_excl_rate,
                suspension_rate=excluded.suspension_rate,
                pct_one_plus_suspension=excluded.pct_one_plus_suspension
        """, excl_rows)
        print(f"  Exclusions rows inserted/updated:   {len(excl_rows)}")

        # Insert applications
        app_rows = [
            (int(r.urn), r.time_period, r.entry_year, r.places_offered,
             r.times_put_as_1st_preference, r.times_put_as_any_preference,
             r.first_preference_offers, r.preferred_offers,
             r.oversubscription_ratio, r.fsm_eligible_pct, r.admissions_policy)
            for r in applications_df.itertuples()
        ]
        cursor.executemany("""
            INSERT INTO applications (urn, time_period, entry_year, places_offered,
                times_put_as_1st_preference, times_put_as_any_preference,
                first_preference_offers, preferred_offers,
                oversubscription_ratio, fsm_eligible_pct, admissions_policy)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(urn, time_period, entry_year) DO UPDATE SET
                places_offered=excluded.places_offered,
                times_put_as_1st_preference=excluded.times_put_as_1st_preference,
                oversubscription_ratio=excluded.oversubscription_ratio,
                fsm_eligible_pct=excluded.fsm_eligible_pct
        """, app_rows)
        print(f"  Applications rows inserted/updated: {len(app_rows)}")

        conn.commit()

    print(f"\nDone. Database: {DB_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    absence_file      = download(ABSENCE_URL,     ABSENCE_FILENAME)
    exclusions_file   = download(EXCLUSIONS_URL,  EXCLUSIONS_FILENAME)
    applications_file = DATA_DIR / APPLICATIONS_FILENAME

    if not applications_file.exists():
        raise FileNotFoundError(
            f"Applications file not found at {applications_file}\n"
            "Please copy AppsandOffers_2024_SchoolLevel.csv into the data/ folder."
        )

    absence_df      = process_absence(absence_file)
    exclusions_df   = process_exclusions(exclusions_file)
    applications_df = process_applications(applications_file)

    save_to_sqlite(absence_df, exclusions_df, applications_df)
