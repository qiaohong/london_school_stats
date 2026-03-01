"""
Rightmove URL builder.

URL strategy:
  Rightmove's /in-{outcode}.html is an SEO browse page that does not
  reliably process query parameters — hence the redirect to home page.
  The correct search endpoint is /property-for-sale/find.html with a
  locationIdentifier. Since Rightmove's autocomplete API returns 404,
  we use the outcode text directly in the locationIdentifier field.
  This resolves correctly for all standard London outcodes.

  Format: find.html?locationIdentifier=OUTCODE%5E{OUTCODE}&radius=...
  %5E = ^ (caret), which Rightmove uses as a prefix separator.
"""

from urllib.parse import urlencode

# Rightmove supported radius values (miles)
_RM_RADII = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0]


def _nearest_rm_radius(miles: float) -> float:
    return min(_RM_RADII, key=lambda r: abs(r - miles))


def _km_to_miles(km: float) -> float:
    return km * 0.621371


def _postcode_to_outcode(postcode: str) -> str:
    """Extract outcode (uppercase) from a full UK postcode. E.g. 'N8 9DP' → 'N8'."""
    return postcode.strip().split()[0].upper()


def build_url(
    postcode: str,
    cutoff_km: float | None = None,
    max_price: int | None = None,
    min_bedrooms: int | None = None,
    listing_type: str = "sale",
) -> str:
    """
    Build a Rightmove search URL near the given school postcode.

    Uses find.html with locationIdentifier=OUTCODE^{outcode} so that
    Rightmove's search engine resolves the area correctly and applies
    radius/price filters.
    """
    outcode = _postcode_to_outcode(postcode)
    path = "property-for-sale" if listing_type == "sale" else "property-to-rent"

    if cutoff_km is not None:
        target_miles = _km_to_miles(cutoff_km * 1.2)
    else:
        target_miles = 0.5

    radius = _nearest_rm_radius(target_miles)

    params = {
        "locationIdentifier": f"OUTCODE^{outcode}",
        "radius": radius,
        "sortType": 6,
        "includeSSTC": "false",
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
