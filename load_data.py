"""
load_data.py — Load UK school performance data into SQLite and build London model.

Phase 1A: Load raw CSVs   → raw_*  tables
Phase 1B: Load raw XLSXs  → raw_*  tables  (skips large underlying files)
Phase 1C: Load metadata   → meta_* tables
Phase 2:  Identify London LA codes from metadata
Phase 3:  Build London-only model tables with cleaning applied

Cleaning rules applied in Phase 3:
- DfE suppression markers (SUPP, NE, NP, LOW) → NaN
- KS2: legacy columns >=50% null dropped (discontinued KS1 prior attainment measures)
- KS5: FE colleges excluded (keep school-based sixth forms only)
"""

import os
import re
import sqlite3
import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH  = os.path.join(BASE_DIR, "schools.db")

YEAR_FOLDERS = ["2022-2023", "2023-2024", "2024-2025"]

# DfE suppression markers → treated as NaN in model tables
SUPP_VALUES = {"SUPP", "NE", "NP", "LOW"}

# XLSX stems to skip in Phase 1B (large underlying files; not needed for school-level summaries)
SKIP_XLSX_STEMS = {
    "ks4underlying_1",
    "ks4underlying_entriesandgrades_2",
    "ks5underlying",
    "apprentice_achievement_rates",
}

# FE college type string in KS5 NFTYPE/FESITYPE column (excluded from ks5_results)
FE_COLLEGE_TYPE = "General Further Education College"

# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitise(name: str) -> str:
    """Convert a string to a safe SQLite identifier segment."""
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower()


def year_key(year_folder: str) -> str:
    """'2022-2023' → '2022_2023'"""
    return year_folder.replace("-", "_")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def load_df_to_db(conn: sqlite3.Connection, df: pd.DataFrame, table: str) -> int:
    """Write dataframe to SQLite, replacing any existing table. Returns row count."""
    df.to_sql(table, conn, if_exists="replace", index=False)
    return len(df)


def read_csv_with_fallback(fpath: str) -> pd.DataFrame:
    """Read CSV, falling back to latin-1 if UTF-8 fails."""
    try:
        return pd.read_csv(fpath, low_memory=False, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(fpath, low_memory=False, encoding="latin-1")


def norm_numeric_col(series: pd.Series) -> pd.Series:
    """
    Normalise a numeric ID column (URN / LA) to integer values,
    dropping NaN. Handles both int64 and float64 columns.
    Returns a Series of Python ints with the same index (NaN rows dropped).
    """
    return pd.to_numeric(series, errors="coerce").dropna().astype(int)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# ── Phase 1A: Load raw CSVs ───────────────────────────────────────────────────

def load_raw_csvs(conn: sqlite3.Connection):
    print("\n=== Phase 1A: Loading raw CSVs ===")
    for year in YEAR_FOLDERS:
        year_dir = os.path.join(DATA_DIR, year)
        yk = year_key(year)
        for fname in sorted(os.listdir(year_dir)):
            if not fname.lower().endswith(".csv"):
                continue
            fpath = os.path.join(year_dir, fname)
            stem = fname[len("england_"):] if fname.startswith("england_") else fname
            stem = sanitise(os.path.splitext(stem)[0])
            table = f"raw_{yk}_{stem}"
            size_mb = os.path.getsize(fpath) / 1_048_576
            print(f"  loading {table} ({size_mb:.1f} MB)...", end=" ", flush=True)
            try:
                df = read_csv_with_fallback(fpath)
                df = df.assign(source_year=year)
                n = load_df_to_db(conn, df, table)
                print(f"{n:,} rows, {len(df.columns)} cols")
            except Exception as e:
                print(f"ERROR: {e}")


# ── Phase 1B: Load raw XLSXs ─────────────────────────────────────────────────

def load_raw_xlsxs(conn: sqlite3.Connection):
    print("\n=== Phase 1B: Loading raw XLSXs ===")
    for year in YEAR_FOLDERS:
        year_dir = os.path.join(DATA_DIR, year)
        yk = year_key(year)
        for fname in sorted(os.listdir(year_dir)):
            if not fname.lower().endswith(".xlsx"):
                continue
            fpath = os.path.join(year_dir, fname)
            stem = fname[len("england_"):] if fname.startswith("england_") else fname
            stem = sanitise(os.path.splitext(stem)[0])
            if stem in SKIP_XLSX_STEMS:
                print(f"  skipping {fname} (underlying file, not needed for summaries)")
                continue
            size_mb = os.path.getsize(fpath) / 1_048_576
            print(f"  loading {fname} ({size_mb:.1f} MB)...", flush=True)
            try:
                xf = pd.ExcelFile(fpath)
                sheets = xf.sheet_names
                for sheet in sheets:
                    print(f"    sheet '{sheet}'...", end=" ", flush=True)
                    df = xf.parse(sheet)
                    df = df.assign(source_year=year)
                    if len(sheets) == 1:
                        table = f"raw_{yk}_{stem}"
                    else:
                        table = f"raw_{yk}_{stem}_{sanitise(str(sheet))}"
                    n = load_df_to_db(conn, df, table)
                    print(f"{n:,} rows → {table}")
            except Exception as e:
                print(f"  ERROR loading {fpath}: {e}")


# ── Phase 1C: Load metadata ───────────────────────────────────────────────────

def load_metadata(conn: sqlite3.Connection):
    print("\n=== Phase 1C: Loading metadata ===")
    meta_dir = os.path.join(DATA_DIR, "metadata")
    for fname in sorted(os.listdir(meta_dir)):
        fpath = os.path.join(meta_dir, fname)
        ext = fname.lower().rsplit(".", 1)[-1]
        stem = sanitise(os.path.splitext(fname)[0])
        table_base = f"meta_{stem}"
        try:
            if ext == "csv":
                df = read_csv_with_fallback(fpath)
                n = load_df_to_db(conn, df, table_base)
                print(f"  {table_base}: {n:,} rows")
            elif ext == "xlsx":
                xf = pd.ExcelFile(fpath)
                sheets = xf.sheet_names
                for sheet in sheets:
                    df = xf.parse(sheet)
                    table = table_base if len(sheets) == 1 else f"{table_base}_{sanitise(str(sheet))}"
                    n = load_df_to_db(conn, df, table)
                    print(f"  {table}: {n:,} rows")
        except Exception as e:
            print(f"  ERROR loading {fpath}: {e}")


# ── Phase 2: Identify London LA codes ─────────────────────────────────────────

def get_london_la_codes(conn: sqlite3.Connection) -> set:
    """Return set of integer LA codes for all London authorities."""
    try:
        df = pd.read_sql(
            'SELECT LEA, "REGION NAME" AS region_name FROM meta_la_and_region_codes_meta',
            conn,
        )
        london = df[df["region_name"].str.contains("London", case=False, na=False)]
        codes = set(norm_numeric_col(london["LEA"]).tolist())
        if codes:
            print(f"\n=== Phase 2: Found {len(codes)} London LA codes from metadata ===")
            return codes
    except Exception as e:
        print(f"  Warning: Could not read metadata LA table: {e}")

    # Fallback: well-known London LA code ranges
    print("\n=== Phase 2: Using fallback London LA code ranges ===")
    codes = set(range(201, 214)) | set(range(301, 333))
    print(f"  Using {len(codes)} codes (201-213, 301-332)")
    return codes


# ── Phase 3: Build London-only model ──────────────────────────────────────────

def get_london_urns(conn: sqlite3.Connection, london_la_codes: set) -> set:
    """Collect all URNs for London schools across all years (as integers)."""
    urns: set = set()
    la_int_set = {int(c) for c in london_la_codes}
    for year in YEAR_FOLDERS:
        yk = year_key(year)
        table = f"raw_{yk}_school_information"
        if not table_exists(conn, table):
            continue
        try:
            df = pd.read_sql(f'SELECT URN, LA FROM [{table}]', conn)
            la_norm = norm_numeric_col(df["LA"])
            # Keep rows where LA is a London code
            mask = la_norm.isin(la_int_set)
            london_rows = df.loc[la_norm.index[mask]]
            urn_vals = norm_numeric_col(london_rows["URN"])
            urns.update(urn_vals.tolist())
        except Exception as e:
            print(f"  Warning: Could not read {table}: {e}")
    print(f"  Found {len(urns):,} unique London URNs across all years")
    return urns


def combine_tables(
    conn: sqlite3.Connection,
    raw_suffixes: list,
    filter_col: str,
    filter_values: set,
) -> pd.DataFrame:
    """
    Search for raw tables matching any of the given suffixes across all years.
    Filters rows where `filter_col` is in `filter_values` (integer comparison).
    Returns combined dataframe with 'academic_year' column.
    """
    int_values = {int(v) for v in filter_values}
    frames = []
    for year in YEAR_FOLDERS:
        yk = year_key(year)
        for suffix in raw_suffixes:
            table = f"raw_{yk}_{suffix}"
            if not table_exists(conn, table):
                continue
            try:
                df = pd.read_sql(f"SELECT * FROM [{table}]", conn)
                df["academic_year"] = year
                if filter_col in df.columns:
                    col_norm = norm_numeric_col(df[filter_col])
                    mask = col_norm.isin(int_values)
                    df = df.loc[col_norm.index[mask]]
                # else: no filter column present — include all rows
                frames.append(df)
                break  # first matching suffix wins per year
            except Exception as e:
                print(f"    Warning: {table}: {e}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def clean_model_df(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """
    Apply agreed cleaning rules to a model dataframe:
      1. Replace DfE suppression markers with NaN (all tables)
      2. Drop legacy columns >=50% null (ks2_results only)
      3. Exclude FE colleges (ks5_results only)
    """
    # 1. Suppression markers → NaN
    for col in df.select_dtypes(include="object").columns:
        mask = df[col].str.strip().isin(SUPP_VALUES)
        df[col] = df[col].where(~mask, other=np.nan)

    # 2. KS2: drop legacy columns >=50% null (discontinued KS1 prior attainment measures)
    if table_name == "ks2_results":
        null_frac = df.isnull().mean()
        always_keep = {"URN", "LEA", "ESTAB", "academic_year", "source_year"}
        drop_cols = [
            c for c in null_frac[null_frac >= 0.5].index
            if c not in always_keep
        ]
        if drop_cols:
            print(f"    Dropping {len(drop_cols)} high-null legacy KS2 columns")
            df = df.drop(columns=drop_cols)

    # 3. KS5: exclude FE colleges (keep school-based sixth forms only)
    if table_name == "ks5_results":
        fe_col = "NFTYPE/FESITYPE"
        if fe_col in df.columns:
            before = len(df)
            df = df[df[fe_col] != FE_COLLEGE_TYPE]
            removed = before - len(df)
            if removed:
                print(f"    Removed {removed} FE college rows from ks5_results")

    return df


def build_london_model(conn: sqlite3.Connection, london_la_codes: set, london_urns: set):
    print("\n=== Phase 3: Building London-only model tables ===")

    # (output_table, [raw_suffixes_to_try], filter_col, filter_values)
    model_tables = [
        ("schools",                  ["school_information"],      "LA",  london_la_codes),
        ("ks4_results",              ["ks4final", "ks4revised"],  "URN", london_urns),
        ("ks2_results",              ["ks2final", "ks2revised"],  "URN", london_urns),
        ("ks5_results",              ["ks5final", "ks5revised"],  "URN", london_urns),
        ("census",                   ["census"],                  "URN", london_urns),
        ("absences",                 ["abs"],                     "URN", london_urns),
        ("ks4_pupil_destinations",   ["ks4_pupdest"],             "URN", london_urns),
        ("ks5_student_destinations", ["ks5_studest"],             "URN", london_urns),
    ]

    for out_table, suffixes, filter_col, filter_values in model_tables:
        df = combine_tables(conn, suffixes, filter_col, filter_values)
        if df.empty:
            print(f"  {out_table}: no data found (source tables may be missing)")
            continue
        df = clean_model_df(df, out_table)
        load_df_to_db(conn, df, out_table)
        years_present = sorted(df["academic_year"].unique().tolist())
        print(f"  {out_table}: {len(df):,} rows, years={years_present}")

    conn.commit()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Database: {DB_PATH}")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Removed existing schools.db")

    conn = get_connection()
    try:
        load_raw_csvs(conn)
        conn.commit()

        load_raw_xlsxs(conn)
        conn.commit()

        load_metadata(conn)
        conn.commit()

        london_la_codes = get_london_la_codes(conn)
        london_urns     = get_london_urns(conn, london_la_codes)
        build_london_model(conn, london_la_codes, london_urns)

        # Summary
        tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn
        )["name"]
        raw_count   = tables.str.startswith("raw_").sum()
        meta_count  = tables.str.startswith("meta_").sum()
        model_count = len(tables) - raw_count - meta_count

        print(f"\n=== Done ===")
        print(f"  Total tables  : {len(tables)}")
        print(f"  raw_* tables  : {raw_count}")
        print(f"  meta_* tables : {meta_count}")
        print(f"  model tables  : {model_count}")
        print(f"  Database path : {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
