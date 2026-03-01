"""
Commute time estimator using heuristics (no live API).

Approach:
  - Each LA has a pre-profiled centroid lat/lng and transit quality.
  - Straight-line distance from work postcode to LA centroid is computed.
  - Commute time is estimated via: base_time + distance * speed_factor
  - Speed factor varies by transit type (tube fastest, rail slower, overground medium).
  - Result is a (min_minutes, max_minutes) range.
"""

import json
import math
import os
import requests

_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "la_commute_profile.json")

_TRANSIT_SPEED = {
    "tube": 0.38,       # km/min (~23 km/h including waits)
    "dlr": 0.34,
    "overground": 0.30,
    "rail": 0.28,       # slower + less frequent penalty
}

_TRANSIT_VARIANCE = {
    "tube": (0.80, 1.25),
    "dlr": (0.80, 1.30),
    "overground": (0.75, 1.35),
    "rail": (0.70, 1.40),
}

BASE_TRANSFER_MIN = 10  # walk to station + wait


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance in km between two lat/lng points."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def load_profiles() -> list[dict]:
    with open(_PROFILE_PATH) as f:
        return json.load(f)


def resolve_postcode(postcode: str) -> tuple[float, float] | None:
    """Return (lat, lng) for a UK postcode using postcodes.io. Returns None on failure."""
    try:
        resp = requests.get(
            f"https://api.postcodes.io/postcodes/{postcode.replace(' ', '')}",
            timeout=5,
        )
        data = resp.json()
        if data.get("status") == 200:
            return data["result"]["latitude"], data["result"]["longitude"]
        # Try outward code fallback
        outward = postcode.strip().split()[0] if " " in postcode else postcode[:4].strip()
        resp2 = requests.get(
            f"https://api.postcodes.io/outcodes/{outward}",
            timeout=5,
        )
        data2 = resp2.json()
        if data2.get("status") == 200:
            return data2["result"]["latitude"], data2["result"]["longitude"]
    except Exception:
        pass
    return None


def estimate_commute(la: dict, work_lat: float, work_lng: float) -> tuple[int, int]:
    """
    Return (min_minutes, max_minutes) commute estimate from work location to an LA.
    """
    dist_km = _haversine_km(work_lat, work_lng, la["centroid_lat"], la["centroid_lng"])
    transit = la.get("transit", "rail")
    speed = _TRANSIT_SPEED.get(transit, 0.28)
    mid = BASE_TRANSFER_MIN + dist_km / speed
    lo_f, hi_f = _TRANSIT_VARIANCE.get(transit, (0.75, 1.40))
    return (max(5, int(mid * lo_f)), int(mid * hi_f))


def filter_las_by_commute(
    work_lat: float,
    work_lng: float,
    limit_minutes: int,
    flex_minutes: int = 0,
) -> list[dict]:
    """
    Return all LAs whose estimated max commute ≤ (limit_minutes + flex_minutes),
    sorted by estimated mid-point commute ascending.
    Each LA dict gains 'commute_min' and 'commute_max' keys.
    """
    profiles = load_profiles()
    effective_limit = limit_minutes + flex_minutes
    results = []

    for la in profiles:
        mn, mx = estimate_commute(la, work_lat, work_lng)
        mid = (mn + mx) / 2
        if mn <= effective_limit:  # at least the fast end is feasible
            results.append({**la, "commute_min": mn, "commute_max": mx, "_mid": mid})

    results.sort(key=lambda x: x["_mid"])
    for r in results:
        del r["_mid"]
    return results


def top_las(
    work_lat: float,
    work_lng: float,
    limit_minutes: int,
    flex_minutes: int = 0,
    n: int = 3,
) -> list[dict]:
    """Return up to n best-matching LAs for commute criteria."""
    return filter_las_by_commute(work_lat, work_lng, limit_minutes, flex_minutes)[:n]
