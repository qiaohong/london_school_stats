"""
Child birth date → UK year group → school stages logic.
UK school year starts in September. Children must be 5 by 31 August to start Year 1
(Reception at age 4-5, Year 1 at age 5-6, etc.).
"""

from datetime import date


def _academic_year_start() -> int:
    """Return the calendar year of the current academic year start (September)."""
    today = date.today()
    return today.year if today.month >= 9 else today.year - 1


def birth_to_year_group(birth_year: int, birth_month: int) -> int | None:
    """
    Convert a child's birth year/month to their current UK year group.
    Returns an integer: -1 = Nursery, 0 = Reception, 1–13 = Year 1–13.
    Returns None if the child has left school (>18) or not yet born.
    """
    academic_start = _academic_year_start()
    # Age at the start of this academic year (1 September)
    age_at_sept = academic_start - birth_year
    if birth_month > 8:  # born after August: one year younger in that academic year
        age_at_sept -= 1

    # Year group = age - 4 (Reception = age 4 turning 5)
    year_group = age_at_sept - 4

    if year_group < -1:
        return None  # Not yet school age (nursery-eligible in future)
    if year_group > 13:
        return None  # Left school

    return year_group


def year_group_label(yg: int) -> str:
    """Human-readable label for a year group integer."""
    if yg == -1:
        return "Nursery"
    if yg == 0:
        return "Reception"
    return f"Year {yg}"


def year_group_to_phase(yg: int) -> str:
    """Map a year group to school phase."""
    if yg < 0:
        return "Nursery"
    if yg <= 6:
        return "Primary (KS1/KS2)"
    if yg <= 11:
        return "Secondary (KS3/KS4)"
    if yg <= 13:
        return "Sixth Form (KS5)"
    return "Unknown"


def relevant_phases(birth_year: int, birth_month: int) -> list[dict]:
    """
    Return the school phases relevant for a child now and in the next 3 years.
    Each entry: {year_group, label, phase, years_from_now, transition}
    """
    current_yg = birth_to_year_group(birth_year, birth_month)
    if current_yg is None:
        return []

    seen_phases = set()
    result = []

    for offset in range(4):  # current year + 3 ahead
        yg = current_yg + offset
        if yg > 13:
            break

        phase = year_group_to_phase(yg)
        transition = None

        if offset > 0:
            prev_phase = year_group_to_phase(yg - 1)
            if prev_phase != phase:
                transition = f"Transitions to {phase} in {offset} year{'s' if offset > 1 else ''}"

        entry = {
            "year_group": yg,
            "label": year_group_label(yg),
            "phase": phase,
            "years_from_now": offset,
            "transition": transition,
        }

        # Only add each phase once (first time we encounter it)
        if phase not in seen_phases:
            seen_phases.add(phase)
            result.append(entry)
        elif transition:
            # Add transition markers even for already-seen phases
            result.append(entry)

    return result


def phases_to_ks_keys(phases: list[dict]) -> list[str]:
    """Convert phase list to DB query keys: 'ks2', 'ks4', 'ks5'."""
    mapping = {
        "Primary (KS1/KS2)": "ks2",
        "Secondary (KS3/KS4)": "ks4",
        "Sixth Form (KS5)": "ks5",
    }
    keys = []
    for p in phases:
        k = mapping.get(p["phase"])
        if k and k not in keys:
            keys.append(k)
    return keys
