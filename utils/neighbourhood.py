"""
Neighbourhood data utilities:
  - Batch postcode → lat/lng geocoding (postcodes.io)
  - Crime data from data.police.uk (1-mile radius, per month)
  - Static house price lookup by LA name
"""

import json
import os
import requests

_PRICES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "la_house_prices.json")

with open(_PRICES_PATH) as f:
    _LA_PRICES = json.load(f)

CRIME_CATEGORY_LABELS = {
    "anti-social-behaviour":  "Anti-social behaviour",
    "bicycle-theft":          "Bicycle theft",
    "burglary":               "Burglary",
    "criminal-damage-arson":  "Criminal damage",
    "drugs":                  "Drugs",
    "other-crime":            "Other crime",
    "other-theft":            "Other theft",
    "possession-of-weapons":  "Weapons",
    "public-order":           "Public order",
    "robbery":                "Robbery",
    "shoplifting":            "Shoplifting",
    "theft-from-the-person":  "Theft (person)",
    "vehicle-crime":          "Vehicle crime",
    "violent-crime":          "Violent crime",
}

# Categories we highlight as most relevant to families
PRIORITY_CATEGORIES = {"burglary", "violent-crime", "robbery", "anti-social-behaviour"}


def batch_geocode(postcodes: list[str]) -> dict[str, tuple[float, float]]:
    """
    Geocode a list of UK postcodes via postcodes.io bulk POST.
    Returns {postcode: (lat, lng)} for those successfully resolved.
    """
    if not postcodes:
        return {}

    # Deduplicate
    unique = list({pc.strip().upper() for pc in postcodes if pc})
    result = {}

    # postcodes.io allows up to 100 per batch
    for i in range(0, len(unique), 100):
        batch = unique[i : i + 100]
        try:
            resp = requests.post(
                "https://api.postcodes.io/postcodes",
                json={"postcodes": batch},
                timeout=10,
            )
            data = resp.json()
            for item in data.get("result", []):
                if item and item.get("result"):
                    pc = item["query"].strip().upper()
                    result[pc] = (item["result"]["latitude"], item["result"]["longitude"])
        except Exception:
            pass

    return result


def get_latest_crime_month() -> str:
    """Return the most recently available crime month string (YYYY-MM)."""
    try:
        resp = requests.get("https://data.police.uk/api/crimes-street-dates", timeout=5)
        dates = resp.json()
        if dates:
            return dates[0]["date"]  # descending order → first = latest
    except Exception:
        pass
    return "2026-01"


def get_crime_data(lat: float, lng: float, month: str) -> dict:
    """
    Fetch all crimes within ~1 mile of (lat, lng) for the given month.
    Returns:
        {
            'total': int,
            'by_category': {category_slug: count},
            'month': str,
        }
    """
    try:
        resp = requests.get(
            "https://data.police.uk/api/crimes-street/all-crime",
            params={"lat": lat, "lng": lng, "date": month},
            timeout=10,
        )
        crimes = resp.json()
        if not isinstance(crimes, list):
            return {"total": 0, "by_category": {}, "month": month}

        by_cat: dict[str, int] = {}
        for c in crimes:
            cat = c.get("category", "other-crime")
            by_cat[cat] = by_cat.get(cat, 0) + 1

        return {"total": len(crimes), "by_category": by_cat, "month": month}
    except Exception:
        return {"total": 0, "by_category": {}, "month": month}


def crime_label(total: int) -> tuple[str, str]:
    """Return (text, colour) classification for a crime count (per month, 1-mile radius)."""
    if total < 400:
        return "Low", "green"
    elif total < 700:
        return "Moderate", "orange"
    elif total < 1000:
        return "High", "red"
    else:
        return "Very high", "red"


def house_price_for_la(la_name: str) -> int | None:
    """Return approximate 2024 median house price for a London LA, or None."""
    return _LA_PRICES.get(la_name)
