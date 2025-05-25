# Auto-generated constants for attribute classification
# Physics units grouped by dimension
PHYSICS_UNITS = {
    "length": ["mm", "cm", "m", "in", "ft"],
    "mass": ["g", "kg", "lb", "ton", "tonne"],
    "force": ["n", "kn", "lbf"],
    "power": ["w", "kw", "hp"],
    "voltage": ["v", "kv"],
    "current": ["a", "ma"],
    "pressure": ["psi", "bar", "kpa", "mpa"],
    "capacity": ["l", "gallon", "gal", "yd³", "m³"],
}

# Flatten for quick lookup
FLAT_UNITS = {u for units in PHYSICS_UNITS.values() for u in units}

# Common brand cues
BRAND_KEYWORDS = {
    "manufacturer", "model", "serial", "part", "sku",
    "brand", "variant", "series", "family"
}

def classify_attr(name: str, sample_value: str | None) -> str:
    """Classify attribute as 'physics' or 'brand' using heuristics."""
    lname = name.lower()
    value = (sample_value or "").lower()

    # Unit-based detection
    if any(f" {u}" in value or value.endswith(u) for u in FLAT_UNITS):
        return "physics"

    # Numeric in value
    if any(ch.isdigit() for ch in value):
        return "physics"

    # Keyword-based brand detection
    if any(kw in lname for kw in BRAND_KEYWORDS):
        return "brand"

    # Physics tokens
    for token in [
        "weight", "height", "width", "length", "power",
        "capacity", "torque", "speed", "voltage", "pressure",
    ]:
        if token in lname:
            return "physics"

    # Default
    return "brand"
