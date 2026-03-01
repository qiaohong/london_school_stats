"""
quality_report.py — Data quality analysis for the London school model.

Outputs a human-readable report covering:
  1. Row counts per table per year
  2. Null analysis (>10% nulls flagged, >50% highlighted)
  3. Outlier detection (values > 3 SD from mean)
  4. Metadata cross-check (undocumented columns)
  5. Consistency checks (URN coverage, year gaps, suppressed values)

Run:
    python quality_report.py 2>&1 | tee quality_report.txt
"""

import os
import re
import sqlite3
import pandas as pd
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "schools.db")

# DfE suppression markers used in UK education data
SUPPRESSED_VALUES = {"SUPP", "NE", "NP", "LOW", "NA", "X", "Z", "SP"}

# London model tables (in display order)
MODEL_TABLES = [
    "schools",
    "ks4_results",
    "ks4_provisional",
    "ks2_results",
    "ks5_results",
    "census",
    "absences",
    "ks4_pupil_destinations",
    "ks5_student_destinations",
    "ks5_student_destinations_he",
    "ks4_mats",
    "ks5_mats",
    "ks2_mats",
    "value_added_qual",
    "value_added_subj",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def hr(char="─", width=80):
    print(char * width)

def section(title: str):
    print()
    hr("═")
    print(f"  {title}")
    hr("═")


def subsection(title: str):
    print(f"\n{'─'*4} {title} {'─'*(74 - len(title))}")


def get_conn() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}\n"
            "Run load_data.py first."
        )
    return sqlite3.connect(DB_PATH)


def list_model_tables(conn: sqlite3.Connection) -> list:
    all_tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn
    )["name"].tolist()
    return [t for t in MODEL_TABLES if t in all_tables]


def load_table(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM [{table}]", conn)


def get_meta_columns(conn: sqlite3.Connection) -> dict:
    """
    Build a dict: table_name → set of documented column names.
    Reads all meta_* tables and tries to extract column name fields.
    """
    meta_tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'meta_%'", conn
    )["name"].tolist()

    # Common column-name fields in DfE metadata files
    col_fields = ["Field", "field", "Column", "column", "Variable", "variable",
                  "Column Name", "column_name", "Field name", "Fieldname"]

    result = {}
    for mt in meta_tables:
        try:
            df = pd.read_sql(f"SELECT * FROM [{mt}]", conn)
            for cf in col_fields:
                if cf in df.columns:
                    cols = df[cf].dropna().astype(str).str.strip().tolist()
                    # Map to approximate model table name
                    key = re.sub(r"^meta_", "", mt).replace("_meta", "")
                    result.setdefault(key, set()).update(cols)
                    break
        except Exception:
            pass
    return result


# ── Section 1: Row counts ─────────────────────────────────────────────────────

def report_row_counts(conn: sqlite3.Connection, tables: list):
    section("1. ROW COUNTS PER TABLE PER YEAR")

    all_years = ["2022-2023", "2023-2024", "2024-2025"]

    for table in tables:
        try:
            df = load_table(conn, table)
            total = len(df)
            if "academic_year" in df.columns:
                by_year = df.groupby("academic_year").size().to_dict()
                year_str = "  ".join(
                    f"{y}: {by_year.get(y, 0):>6,}" for y in all_years
                )
                print(f"  {table:<40} total={total:>7,}   {year_str}")
            else:
                print(f"  {table:<40} total={total:>7,}   (no academic_year column)")
        except Exception as e:
            print(f"  {table:<40} ERROR: {e}")


# ── Section 2: Null analysis ──────────────────────────────────────────────────

def report_nulls(conn: sqlite3.Connection, tables: list):
    section("2. NULL ANALYSIS  (columns with >10% nulls)")

    for table in tables:
        try:
            df = load_table(conn, table)
            n = len(df)
            if n == 0:
                print(f"\n  {table}: (empty)")
                continue

            null_pct = (df.isnull().sum() / n * 100).sort_values(ascending=False)
            flagged = null_pct[null_pct > 10]
            if flagged.empty:
                print(f"  {table}: all columns <10% null  ✓")
                continue

            print(f"\n  {table}  ({n:,} rows)")
            for col, pct in flagged.items():
                marker = "  *** >50% NULL ***" if pct > 50 else ""
                print(f"    {col:<50} {pct:5.1f}%{marker}")

        except Exception as e:
            print(f"  {table}: ERROR — {e}")


# ── Section 3: Outlier detection ─────────────────────────────────────────────

def report_outliers(conn: sqlite3.Connection, tables: list):
    section("3. OUTLIER DETECTION  (numeric values > 3 SD from mean)")

    for table in tables:
        try:
            df = load_table(conn, table)
            if df.empty:
                continue

            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            # Skip obvious ID/code columns
            skip = {"URN", "LA", "LAESTAB", "ESTAB", "source_year"}
            numeric_cols = [c for c in numeric_cols if c not in skip]

            outlier_findings = []
            for col in numeric_cols:
                series = df[col].dropna()
                if len(series) < 10:
                    continue
                mean, std = series.mean(), series.std()
                if std == 0:
                    continue
                n_out = ((series - mean).abs() > 3 * std).sum()
                if n_out > 0:
                    pct = n_out / len(series) * 100
                    outlier_findings.append((col, n_out, pct, series.min(), series.max()))

            if not outlier_findings:
                print(f"  {table}: no outliers detected  ✓")
                continue

            print(f"\n  {table}:")
            for col, n_out, pct, mn, mx in sorted(outlier_findings, key=lambda x: -x[2]):
                print(f"    {col:<50} {n_out:>5} outliers ({pct:.1f}%)  range=[{mn:.2f}, {mx:.2f}]")

        except Exception as e:
            print(f"  {table}: ERROR — {e}")


# ── Section 4: Metadata cross-check ──────────────────────────────────────────

def report_metadata_crosscheck(conn: sqlite3.Connection, tables: list):
    section("4. METADATA CROSS-CHECK  (undocumented columns)")

    meta_cols = get_meta_columns(conn)
    if not meta_cols:
        print("  No metadata column definitions found — skipping cross-check.")
        return

    print(f"  Metadata column definitions loaded for: {sorted(meta_cols.keys())}\n")

    for table in tables:
        # Find matching metadata key (fuzzy: strip underscores/numbers)
        table_stem = re.sub(r"_\d+$", "", table)  # remove trailing _year suffix
        matched_meta = None
        for mk in meta_cols:
            if mk in table_stem or table_stem in mk:
                matched_meta = mk
                break

        if matched_meta is None:
            print(f"  {table:<40} no matching metadata found — skipping")
            continue

        try:
            df = load_table(conn, table)
            data_cols   = set(df.columns) - {"academic_year", "source_year"}
            doc_cols    = meta_cols[matched_meta]
            undocumented = data_cols - doc_cols
            undocumented -= {"URN", "LA", "LAESTAB"}  # always present, rarely in meta

            if undocumented:
                print(f"  {table} (matched meta: '{matched_meta}'):")
                for c in sorted(undocumented):
                    print(f"    UNDOCUMENTED: {c}")
            else:
                print(f"  {table:<40} all columns documented  ✓")

        except Exception as e:
            print(f"  {table}: ERROR — {e}")


# ── Section 5: Consistency checks ────────────────────────────────────────────

def report_consistency(conn: sqlite3.Connection, tables: list):
    section("5. CONSISTENCY CHECKS")

    # 5a: URNs in results tables not in schools
    subsection("5a. URNs in results tables NOT found in 'schools'")
    if "schools" in tables:
        try:
            schools_df = load_table(conn, "schools")
            known_urns = set(schools_df["URN"].dropna().astype(str))

            results_tables = [t for t in tables if t not in (
                "schools", "ks4_mats", "ks5_mats", "ks2_mats"
            )]
            for table in results_tables:
                try:
                    df = load_table(conn, table)
                    if "URN" not in df.columns:
                        continue
                    table_urns = set(df["URN"].dropna().astype(str))
                    missing = table_urns - known_urns
                    if missing:
                        print(f"  {table}: {len(missing)} URNs not in schools  "
                              f"(e.g. {sorted(missing)[:5]})")
                    else:
                        print(f"  {table}: all URNs found in schools  ✓")
                except Exception as e:
                    print(f"  {table}: ERROR — {e}")
        except Exception as e:
            print(f"  Could not load 'schools' table: {e}")
    else:
        print("  'schools' table not found — skipping URN check")

    # 5b: Schools appearing in some years but not others
    subsection("5b. Schools with incomplete year coverage in 'schools'")
    if "schools" in tables:
        try:
            df = load_table(conn, "schools")
            if "academic_year" in df.columns and "URN" in df.columns:
                all_years = sorted(df["academic_year"].unique())
                pivot = df.groupby(["URN", "academic_year"]).size().unstack(fill_value=0)
                # Schools missing from at least one year
                max_years = len(all_years)
                incomplete = pivot[(pivot > 0).sum(axis=1) < max_years]
                print(f"  Schools present in all {max_years} years : "
                      f"{(~pivot.isin([0]).any(axis=1)).sum():,}")
                print(f"  Schools missing from ≥1 year           : {len(incomplete):,}")
                if len(incomplete) > 0 and len(incomplete) <= 20:
                    print(f"  URNs with gaps: {incomplete.index.tolist()}")
                elif len(incomplete) > 20:
                    print(f"  (showing first 20): {incomplete.index.tolist()[:20]}")
            else:
                print("  'schools' table missing URN or academic_year column")
        except Exception as e:
            print(f"  ERROR: {e}")

    # 5c: Suppressed values
    subsection("5c. Suppressed / special values (SUPP, NE, NP, LOW, etc.)")
    for table in tables:
        try:
            df = load_table(conn, table)
            str_cols = df.select_dtypes(include="object").columns
            supp_counts = {}
            for col in str_cols:
                vals = df[col].dropna().astype(str).str.strip().str.upper()
                matches = vals[vals.isin(SUPPRESSED_VALUES)]
                if len(matches) > 0:
                    supp_counts[col] = len(matches)

            if supp_counts:
                total_supp = sum(supp_counts.values())
                top_cols = sorted(supp_counts.items(), key=lambda x: -x[1])[:5]
                top_str  = ", ".join(f"{c}={n:,}" for c, n in top_cols)
                print(f"  {table:<40} {total_supp:>7,} suppressed cells  top: {top_str}")
            else:
                print(f"  {table:<40} no suppressed values found  ✓")

        except Exception as e:
            print(f"  {table}: ERROR — {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("  UK SCHOOL DATA — LONDON MODEL QUALITY REPORT")
    print(f"  Database: {DB_PATH}")
    print("=" * 80)

    conn = get_conn()
    try:
        tables = list_model_tables(conn)
        if not tables:
            print("ERROR: No London model tables found in the database.")
            print("Run load_data.py first.")
            return

        print(f"\n  London model tables found: {len(tables)}")
        for t in tables:
            print(f"    • {t}")

        report_row_counts(conn, tables)
        report_nulls(conn, tables)
        report_outliers(conn, tables)
        report_metadata_crosscheck(conn, tables)
        report_consistency(conn, tables)

        hr("═")
        print("  END OF REPORT")
        hr("═")
        print()

    finally:
        conn.close()


if __name__ == "__main__":
    main()
