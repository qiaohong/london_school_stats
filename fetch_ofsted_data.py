"""
Ofsted School Inspection Data Collector
Fetches the latest inspection data for London and Surrey schools
and stores it in a SQLite database.
"""

import requests
import pandas as pd
import sqlite3
import re
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "ofsted_schools.db"
DATA_DIR = Path(__file__).parent / "data"

OFSTED_PAGE = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "monthly-management-information-ofsteds-school-inspections-outcomes"
)

TARGET_REGIONS = ["London"]
TARGET_AUTHORITIES_PATTERN = r"Surrey"  # catches East Surrey, Surrey Heath etc.
TARGET_PHASES = ["Primary", "Secondary"]

# Regex to extract date from Ofsted CSV filenames, e.g. "...as_at_30_Sep_2025.csv"
_DATE_RE = re.compile(r"(\d{1,2})_([A-Za-z]{3})_(\d{4})\.csv$")


# ── Step 1: Find latest CSV URL ───────────────────────────────────────────────

def _parse_file_date(url):
    """Return a comparable date from an Ofsted CSV filename, or datetime.min if unparseable."""
    m = _DATE_RE.search(url)
    if not m:
        return datetime.min
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
    except ValueError:
        return datetime.min


def find_latest_csv_url():
    print("Fetching Ofsted download page...")
    resp = requests.get(OFSTED_PAGE, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    candidates = [
        a["href"]
        for a in soup.find_all("a", href=True)
        if "assets.publishing.service.gov.uk" in a["href"]
        and "latest_inspections" in a["href"]
        and a["href"].endswith(".csv")
    ]

    if not candidates:
        raise RuntimeError(
            "Could not find a latest inspections CSV link on the Ofsted page. "
            "The page layout may have changed — check: " + OFSTED_PAGE
        )

    url = max(candidates, key=_parse_file_date)
    print(f"Found latest CSV: {url}")
    return url


# ── Step 2: Download CSV ──────────────────────────────────────────────────────

def download_csv(url):
    DATA_DIR.mkdir(exist_ok=True)
    filepath = DATA_DIR / url.split("/")[-1]

    if filepath.exists():
        print(f"Already downloaded: {filepath.name} — skipping.")
    else:
        print(f"Downloading {filepath.name}...")
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        filepath.write_bytes(resp.content)
        print(f"Saved to {filepath}")

    return filepath


# ── Step 3: Load and filter ───────────────────────────────────────────────────

def _parse_date(val):
    """Convert DD/MM/YYYY string to ISO YYYY-MM-DD for correct SQL sorting."""
    if not val or pd.isna(val):
        return None
    try:
        return datetime.strptime(str(val).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return str(val).strip()


def load_and_filter(filepath):
    print("Loading CSV...")
    df = pd.read_csv(filepath, encoding="cp1252", low_memory=False)

    print(f"Total rows: {len(df)}")

    london_mask = df["Region"].str.strip().isin(TARGET_REGIONS)
    surrey_mask = df["Local authority"].str.contains(
        TARGET_AUTHORITIES_PATTERN, case=False, na=False
    )
    phase_mask = df["Ofsted phase"].isin(TARGET_PHASES)

    df_filtered = df[(london_mask | surrey_mask) & phase_mask].copy()
    print(f"Rows after filtering (London + Surrey, Primary/Secondary): {len(df_filtered)}")

    return df_filtered


# ── Step 4: Build schema and insert ──────────────────────────────────────────

# Maps our field names to CSV column headers
COL = {
    # School details
    "urn":                              "URN",
    "name":                             "School name",
    "phase":                            "Ofsted phase",
    "school_type":                      "Type of education",
    "religious_character":              "Designated religious character",
    "admissions_policy":                "Admissions policy",
    "sixth_form":                       "Sixth form",
    "open_date":                        "School open date",
    "local_authority":                  "Local authority",
    "region":                           "Region",
    "postcode":                         "Postcode",
    "parliamentary_constituency":       "Parliamentary constituency",
    "idaci_quintile":                   "The income deprivation affecting children index (IDACI) quintile",
    # Latest full inspection (any framework)
    "inspection_number":                "Inspection number of latest full inspection",
    "inspection_type":                  "Inspection type",
    "inspection_start_date":            "Inspection start date",
    "publication_date":                 "Publication date",
    # OEIF (new framework) grades — used when available
    "oeif_inspection_number":           "Inspection number of latest OEIF graded inspection",
    "oeif_inspection_start_date":       "Inspection start date of latest OEIF graded inspection",
    "oeif_publication_date":            "Publication date of latest OEIF graded inspection",
    "overall_effectiveness":            "Latest OEIF overall effectiveness",
    "quality_of_education":             "Latest OEIF quality of education",
    "behaviour_and_attitudes":          "Latest OEIF behaviour and attitudes",
    "personal_development":             "Latest OEIF personal development",
    "leadership_and_management":        "Latest OEIF effectiveness of leadership and management",
    "early_years_provision":            "Latest OEIF early years provision (where applicable)",
    "sixth_form_provision":             "Latest OEIF sixth form provision (where applicable)",
    "safeguarding_effective":           "Latest OEIF  safeguarding is effective?",
    "category_of_concern":              "Most recent category of concern",
}

DATE_FIELDS = {
    "inspection_start_date", "publication_date",
    "oeif_inspection_start_date", "oeif_publication_date",
}


def _get(row, key):
    """Retrieve a value from a CSV row by our field name, returning None if missing/NaN."""
    csv_col = COL.get(key)
    if csv_col and csv_col in row.index:
        val = row[csv_col]
        return None if pd.isna(val) else val
    return None


def _warn_missing_columns(df):
    csv_cols = set(df.columns)
    for key, csv_col in COL.items():
        if csv_col not in csv_cols:
            print(f"  WARNING: expected column '{csv_col}' not found in CSV (field: {key})")


def save_to_sqlite(df):
    print(f"Saving to SQLite: {DB_PATH}")
    _warn_missing_columns(df)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS schools (
                urn                         INTEGER PRIMARY KEY,
                name                        TEXT NOT NULL,
                phase                       TEXT,
                school_type                 TEXT,
                religious_character         TEXT,
                admissions_policy           TEXT,
                sixth_form                  TEXT,
                open_date                   TEXT,
                local_authority             TEXT,
                region                      TEXT,
                postcode                    TEXT,
                parliamentary_constituency  TEXT,
                idaci_quintile              INTEGER
            );

            CREATE TABLE IF NOT EXISTS inspections (
                id                              INTEGER PRIMARY KEY AUTOINCREMENT,
                urn                             INTEGER NOT NULL REFERENCES schools(urn),
                inspection_number               TEXT UNIQUE,
                inspection_type                 TEXT,
                inspection_start_date           TEXT,   -- ISO: YYYY-MM-DD
                publication_date                TEXT,   -- ISO: YYYY-MM-DD
                oeif_inspection_number          TEXT,
                oeif_inspection_start_date      TEXT,   -- ISO: YYYY-MM-DD
                oeif_publication_date           TEXT    -- ISO: YYYY-MM-DD
            );

            CREATE TABLE IF NOT EXISTS judgements (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id               INTEGER NOT NULL REFERENCES inspections(id),
                -- OEIF (new framework) grades
                overall_effectiveness       TEXT,
                quality_of_education        TEXT,
                behaviour_and_attitudes     TEXT,
                personal_development        TEXT,
                leadership_and_management   TEXT,
                early_years_provision       TEXT,
                sixth_form_provision        TEXT,
                safeguarding_effective      TEXT,
                category_of_concern         TEXT
            );
        """)

        schools_data = []
        inspections_data = []
        judgements_rows = []  # will be populated after inspection IDs are known

        for _, row in df.iterrows():
            urn = _get(row, "urn")
            if not urn:
                continue
            urn = int(urn)

            schools_data.append((
                urn,
                _get(row, "name"),
                _get(row, "phase"),
                _get(row, "school_type"),
                _get(row, "religious_character"),
                _get(row, "admissions_policy"),
                _get(row, "sixth_form"),
                _get(row, "open_date"),
                _get(row, "local_authority"),
                _get(row, "region"),
                _get(row, "postcode"),
                _get(row, "parliamentary_constituency"),
                _get(row, "idaci_quintile"),
            ))

            inspections_data.append((
                urn,
                _get(row, "inspection_number"),
                _get(row, "inspection_type"),
                _parse_date(_get(row, "inspection_start_date")),
                _parse_date(_get(row, "publication_date")),
                _get(row, "oeif_inspection_number"),
                _parse_date(_get(row, "oeif_inspection_start_date")),
                _parse_date(_get(row, "oeif_publication_date")),
                # judgements stored alongside for matching after insert
                _get(row, "overall_effectiveness"),
                _get(row, "quality_of_education"),
                _get(row, "behaviour_and_attitudes"),
                _get(row, "personal_development"),
                _get(row, "leadership_and_management"),
                _get(row, "early_years_provision"),
                _get(row, "sixth_form_provision"),
                _get(row, "safeguarding_effective"),
                _get(row, "category_of_concern"),
            ))

        cursor.executemany("""
            INSERT INTO schools (
                urn, name, phase, school_type, religious_character,
                admissions_policy, sixth_form, open_date, local_authority,
                region, postcode, parliamentary_constituency, idaci_quintile
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(urn) DO UPDATE SET
                name=excluded.name,
                phase=excluded.phase,
                school_type=excluded.school_type,
                local_authority=excluded.local_authority,
                region=excluded.region,
                postcode=excluded.postcode,
                idaci_quintile=excluded.idaci_quintile
        """, schools_data)

        # Insert inspections one at a time so we can capture the rowid for judgements
        for insp in inspections_data:
            cursor.execute("""
                INSERT INTO inspections (
                    urn, inspection_number, inspection_type,
                    inspection_start_date, publication_date,
                    oeif_inspection_number, oeif_inspection_start_date, oeif_publication_date
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(inspection_number) DO NOTHING
            """, insp[:8])

            # Only insert judgements for genuinely new inspections
            if cursor.rowcount == 1:
                inspection_id = cursor.lastrowid
                judgements_rows.append((inspection_id, *insp[8:]))

        if judgements_rows:
            cursor.executemany("""
                INSERT INTO judgements (
                    inspection_id,
                    overall_effectiveness, quality_of_education,
                    behaviour_and_attitudes, personal_development,
                    leadership_and_management, early_years_provision,
                    sixth_form_provision, safeguarding_effective, category_of_concern
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """, judgements_rows)

        conn.commit()

    print(f"Done. Schools inserted/updated: {len(schools_data)}")
    print(f"      Inspections inserted:      {len(judgements_rows)}")
    print(f"      Database: {DB_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    url = find_latest_csv_url()
    filepath = download_csv(url)
    df = load_and_filter(filepath)
    save_to_sqlite(df)
