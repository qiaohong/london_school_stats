"""
Rightmove URL builder.

URL strategy:
  Rightmove requires a numeric locationIdentifier of the form POSTCODE^{id}.
  We resolve this by calling Rightmove's typeahead API with the postcode.
  If the API call fails, we fall back to a bare searchLocation URL which
  lets the user at least land on the right page and re-run the search.

  Real URL example (N1C 4DB, 0.5 mile):
    find.html?searchLocation=N1C+4DB&useLocationIdentifier=true
             &locationIdentifier=POSTCODE%5E4554477&radius=0.5&_includeSSTC=on
"""

import requests
from functools import lru_cache
from urllib.parse import urlencode

# Rightmove supported radius values (miles)
_RM_RADII = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0]


def _nearest_rm_radius(miles: float) -> float:
    return min(_RM_RADII, key=lambda r: abs(r - miles))


def _km_to_miles(km: float) -> float:
    return km * 0.621371


@lru_cache(maxsize=256)
def _resolve_location_identifier(postcode: str) -> str | None:
    """Call Rightmove's typeahead API to get a numeric locationIdentifier.

    Returns e.g. 'POSTCODE^4554477', or None if the call fails.
    """
    try:
        resp = requests.get(
            "https://api.rightmove.co.uk/api/typeAhead/v1/autocomplete",
            params={"query": postcode, "limit": 5},
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.ok:
            for loc in resp.json().get("typeAheadLocations", []):
                loc_id = loc.get("locationIdentifier", "")
                if loc_id.startswith("POSTCODE^"):
                    return loc_id
    except Exception:
        pass
    return None


def build_url(
    postcode: str,
    cutoff_km: float | None = None,
    max_price: int | None = None,
    min_bedrooms: int | None = None,
    listing_type: str = "sale",
) -> str:
    """
    Build a Rightmove search URL near the given school postcode.
    """
    postcode = postcode.strip().upper()
    path = "property-for-sale" if listing_type == "sale" else "property-to-rent"

    if cutoff_km is not None:
        target_miles = _km_to_miles(cutoff_km * 1.2)
    else:
        target_miles = 0.5

    radius = _nearest_rm_radius(target_miles)

    loc_id = _resolve_location_identifier(postcode)

    if loc_id:
        # loc_id is e.g. "POSTCODE^4554477" — urlencode will encode ^ as %5E, which
        # is exactly what Rightmove expects.
        params: dict = {
            "searchLocation": postcode,
            "useLocationIdentifier": "true",
            "locationIdentifier": loc_id,
            "radius": radius,
            "_includeSSTC": "on",
        }
        if max_price:
            params["maxPrice"] = max_price
        if min_bedrooms:
            params["minBedrooms"] = min_bedrooms
    else:
        # Fallback: bare searchLocation — user lands on search page with postcode
        # pre-filled and can hit Search manually.
        params = {
            "searchLocation": postcode,
            "radius": radius,
            "_includeSSTC": "on",
        }
        if max_price:
            params["maxPrice"] = max_price
        if min_bedrooms:
            params["minBedrooms"] = min_bedrooms

    return f"https://www.rightmove.co.uk/{path}/find.html?{urlencode(params)}"


def describe_radius(cutoff_km: float | None) -> str:
    if cutoff_km is not None:
        miles = _km_to_miles(cutoff_km * 1.2)
        radius = _nearest_rm_radius(miles)
        return f"{radius} miles (based on {cutoff_km:.2f} km admission cut-off + 20% buffer)"
    return "0.5 miles (default — no admission cut-off data available)"
