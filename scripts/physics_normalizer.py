#!/usr/bin/env python
"""
Physics Attribute Normalizer

Utility for normalizing physics attributes to their canonical scientific form.
Removes product-specific prefixes and standardizes naming conventions.
"""

import re
from typing import Dict, Tuple, List, Set

# Define canonical physics attributes and their common variations
CANONICAL_PHYSICS_ATTRIBUTES = {
    # Dimensional attributes
    "length": ["length", "height", "width", "depth", "thickness", "diameter"],
    "weight": ["weight", "mass"],
    "volume": ["volume", "capacity"],
    "area": ["area", "surface"],
    
    # Performance attributes
    "power": ["power", "output", "energy"],
    "speed": ["speed", "velocity", "rpm", "rotation"],
    "torque": ["torque", "moment"],
    "pressure": ["pressure", "psi", "bar"],
    "flow_rate": ["flow", "rate", "discharge"],
    "force": ["force", "strength", "impact"],
    
    # Electrical attributes
    "voltage": ["voltage", "volt"],
    "current": ["current", "ampere", "amp"],
    "frequency": ["frequency", "hertz", "hz"],
    "resistance": ["resistance", "ohm"],
    
    # Other physics attributes
    "temperature": ["temperature", "heat", "thermal"],
    "noise": ["noise", "sound", "acoustic", "decibel"],
    "time": ["time", "duration", "period"],
    "angle": ["angle", "degree", "rotation"]
}

# Common product-specific prefixes to strip
PRODUCT_PREFIXES = [
    "tool", "engine", "motor", "machine", "equipment", "device", "system",
    "battery", "tank", "blade", "cutting", "drilling", "lifting", "maximum",
    "min", "max", "operating", "nominal", "rated", "standard", "typical",
    "overall", "total", "net", "gross", "empty", "full", "working", "idle"
]

# Compiled regex for product prefixes
PREFIX_PATTERN = re.compile(r'^(' + '|'.join(PRODUCT_PREFIXES) + r')_', re.IGNORECASE)

# Standard units for physics attributes
STANDARD_UNITS = {
    "length": "m",
    "weight": "kg",
    "volume": "L",
    "area": "m²",
    "power": "W",
    "speed": "m/s",  # or rpm for rotational
    "torque": "N·m",
    "pressure": "Pa",
    "flow_rate": "m³/s",
    "force": "N",
    "voltage": "V",
    "current": "A",
    "frequency": "Hz",
    "resistance": "Ω",
    "temperature": "°C",
    "noise": "dB",
    "time": "s",
    "angle": "°"
}


def normalize_physics_attribute(attr_name: str) -> Tuple[str, str]:
    """
    Normalize a physics attribute name to its canonical form.
    
    Args:
        attr_name: Raw attribute name
        
    Returns:
        Tuple of (normalized_name, canonical_category)
    """
    # Convert to snake_case and lowercase
    normalized = attr_name.lower().replace(' ', '_')
    
    # Remove product-specific prefixes
    normalized = PREFIX_PATTERN.sub('', normalized)
    
    # Find the canonical category
    for canonical, variations in CANONICAL_PHYSICS_ATTRIBUTES.items():
        for variation in variations:
            if variation in normalized:
                return canonical, canonical
    
    # If no match found, return the cleaned attribute name
    return normalized, "other"


def get_standard_unit(canonical_attr: str) -> str:
    """
    Get the standard unit for a canonical physics attribute.
    
    Args:
        canonical_attr: Canonical attribute name
        
    Returns:
        Standard unit string
    """
    return STANDARD_UNITS.get(canonical_attr, "")


def is_scientific_attribute(attr_name: str) -> bool:
    """
    Check if an attribute name represents a scientific/physics concept.
    
    Args:
        attr_name: Attribute name to check
        
    Returns:
        True if it represents a scientific concept
    """
    # Convert to lowercase for matching
    attr_lower = attr_name.lower()
    
    # Check against all canonical attributes and variations
    for canonical, variations in CANONICAL_PHYSICS_ATTRIBUTES.items():
        if canonical in attr_lower:
            return True
        for variation in variations:
            if variation in attr_lower:
                return True
    
    return False
