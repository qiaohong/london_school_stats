"""
Rightmove URL builder.
Opens a property search near a school's postcode with a radius derived
from the school's admission cut-off distance (or a sensible default).
"""


# Rightmove supported radius values (miles)
_RM_RADII = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0]


def _nearest_rm_radius(miles: float) -> float:
    """Snap a distance in miles to the nearest Rightmove radius option."""
    return min(_RM_RADII, key=lambda r: abs(r - miles))


def _km_to_miles(km: float) -> float:
    return km * 0.621371


def _postcode_to_outcode(postcode: str) -> str:
    """Extract outcode (first part) from a full UK postcode. E.g. 'N8 9DP' → 'n8'."""
    return postcode.strip().split()[0].lower()


def build_url(
    postcode: str,
    cutoff_km: float | None = None,
    max_price: int | None = None,
    min_bedrooms: int | None = None,
    property_types: list[str] | None = None,
    listing_type: str = "sale",   # 'sale' | 'rent'
) -> str:
    """
    Build a Rightmove search URL near the given school postcode.

    Args:
        postcode:        School's full postcode (e.g. 'N8 9DP').
        cutoff_km:       Admission cut-off distance in km. Used to set search radius.
                         If None, defaults to 0.8 km (~0.5 miles).
        max_price:       Optional maximum price filter (£).
        min_bedrooms:    Optional minimum bedrooms filter.
        property_types:  Optional list of property types, e.g. ['detached', 'semi-detached'].
        listing_type:    'sale' or 'rent'.
    """
    outcode = _postcode_to_outcode(postcode)
    path = "property-for-sale" if listing_type == "sale" else "property-to-rent"

    # Radius: add 20% buffer to cutoff so you're not right at the edge
    if cutoff_km is not None:
        target_miles = _km_to_miles(cutoff_km * 1.2)
    else:
        target_miles = 0.5  # default: half a mile

    radius = _nearest_rm_radius(target_miles)

    # Base URL (outcode search with radius)
    url = f"https://www.rightmove.co.uk/{path}/in-{outcode}.html?radius={radius}"

    if max_price:
        url += f"&maxPrice={max_price}"
    if min_bedrooms:
        url += f"&minBedrooms={min_bedrooms}"
    if property_types:
        url += f"&propertyTypes={'%2C'.join(property_types)}"

    url += "&sortType=6"   # sort by distance from centre

    return url


def describe_radius(cutoff_km: float | None) -> str:
    """Human-readable description of the radius being used."""
    if cutoff_km is not None:
        miles = _km_to_miles(cutoff_km * 1.2)
        radius = _nearest_rm_radius(miles)
        return f"{radius} miles (based on {cutoff_km:.2f} km admission cut-off + 20% buffer)"
    return "0.5 miles (default — no admission cut-off data available)"
