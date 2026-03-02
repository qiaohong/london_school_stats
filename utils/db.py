"""
SQLite query helpers for schools.db.
"""

import sqlite3
import os

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "schools.db")


def get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Ofsted ratings we surface in the UI (collapse edge cases)
OFSTED_CLEAN = {
    "Outstanding": "Outstanding",
    "Good": "Good",
    "Requires improvement": "Requires improvement",
    "Inadequate": "Inadequate",
    "Special Measures": "Inadequate",
    "Serious Weaknesses": "Inadequate",
}

# Faith groupings: display label → list of raw RELCHAR values to match
FAITH_GROUPS = {
    "No faith": ["Does not apply", None, ""],
    "Catholic / Roman Catholic": ["Catholic", "Roman Catholic"],
    "Church of England": ["Church of England", "Church of England/Christian", "Christian", "Free Church", "Methodist"],
    "Jewish": ["Jewish", "Orthodox Jewish", "Charadi Jewish"],
    "Muslim / Islamic": ["Muslim", "Islam"],
    "Hindu": ["Hindu"],
    "Sikh": ["Sikh"],
    "Other / Multi-faith": ["Multi-faith", "Greek Orthodox"],
}


def query_schools(
    la_codes: list[int],
    ks_key: str,                    # 'ks2' | 'ks4' | 'ks5'
    ofsted_ratings: list[str],      # e.g. ['Outstanding', 'Good']
    school_types: list[str],        # MINORGROUP values
    admpol: str,                    # 'Any' | 'Selective' | 'Non-selective'
    gender: str,                    # 'Any' | 'Mixed' | 'Boys' | 'Girls'
    faith_groups: list[str],        # display-label keys from FAITH_GROUPS
    include_no_ofsted: bool = True,
) -> list[dict]:
    """
    Query metrics_{ks_key} filtered by user criteria.
    Returns list of row dicts.
    """
    table = f"metrics_{ks_key}"
    conn = get_conn()
    cur = conn.cursor()

    conditions = []
    params = []

    # LA filter
    if la_codes:
        placeholders = ",".join("?" * len(la_codes))
        conditions.append(f"m.LA IN ({placeholders})")
        params.extend(la_codes)

    # School type
    if school_types:
        placeholders = ",".join("?" * len(school_types))
        conditions.append(f"m.MINORGROUP IN ({placeholders})")
        params.extend(school_types)

    # Admissions policy
    if admpol != "Any":
        conditions.append("m.ADMPOL = ?")
        params.append(admpol)

    # Gender
    if gender != "Any":
        conditions.append("m.GENDER = ?")
        params.append(gender)

    # Faith: expand selected groups to raw RELCHAR values
    if faith_groups:
        relchar_vals = []
        include_null = False
        for group in faith_groups:
            for raw in FAITH_GROUPS.get(group, []):
                if raw is None or raw == "":
                    include_null = True
                else:
                    relchar_vals.append(raw)

        faith_conds = []
        if relchar_vals:
            placeholders = ",".join("?" * len(relchar_vals))
            faith_conds.append(f"m.RELCHAR IN ({placeholders})")
            params.extend(relchar_vals)
        if include_null:
            faith_conds.append("(m.RELCHAR IS NULL OR m.RELCHAR = '')")
        if faith_conds:
            conditions.append("(" + " OR ".join(faith_conds) + ")")

    # Ofsted: join schools table using latest inspection per URN
    # Expand selected display ratings to raw DB values
    raw_ofsted = []
    for display_rating in ofsted_ratings:
        for raw, cleaned in OFSTED_CLEAN.items():
            if cleaned == display_rating and raw not in raw_ofsted:
                raw_ofsted.append(raw)

    ofsted_join = (
        "LEFT JOIN ("
        "  SELECT URN, OFSTEDRATING, OFSTEDLASTINSP"
        "  FROM schools"
        "  WHERE OFSTEDRATING IS NOT NULL"
        "  GROUP BY URN"
        "  HAVING MAX(academic_year)"
        ") s ON m.URN = s.URN"
    )
    if raw_ofsted and not include_no_ofsted:
        placeholders = ",".join("?" * len(raw_ofsted))
        conditions.append(f"s.OFSTEDRATING IN ({placeholders})")
        params.extend(raw_ofsted)
    elif raw_ofsted and include_no_ofsted:
        placeholders = ",".join("?" * len(raw_ofsted))
        conditions.append(
            f"(s.OFSTEDRATING IN ({placeholders}) OR s.OFSTEDRATING IS NULL)"
        )
        params.extend(raw_ofsted)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Select all metrics columns + Ofsted from join
    sql = f"""
        SELECT
            m.*,
            s.OFSTEDRATING,
            s.OFSTEDLASTINSP
        FROM {table} m
        {ofsted_join}
        WHERE {where_clause}
        ORDER BY m.composite_score DESC
    """

    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def la_name_to_code(la_names: list[str]) -> list[int]:
    """Convert LA name strings to integer LA codes from the DB."""
    conn = get_conn()
    cur = conn.cursor()
    codes = []
    for name in la_names:
        cur.execute(
            "SELECT DISTINCT LA FROM metrics_ks2 WHERE LANAME=? LIMIT 1",
            (name,),
        )
        row = cur.fetchone()
        if row:
            codes.append(row[0])
        else:
            # Try ks4
            cur.execute(
                "SELECT DISTINCT LA FROM metrics_ks4 WHERE LANAME=? LIMIT 1",
                (name,),
            )
            row = cur.fetchone()
            if row:
                codes.append(row[0])
    conn.close()
    return codes
