#!/usr/bin/env python
"""
Physics Attribute Normalizer

Utility for normalizing physics attributes to their canonical scientific form.
Removes product-specific prefixes and standardizes naming conventions.
"""

import re
from typing import Dict, Tuple, List, Set

# Define subcategories for physics attributes based on scientific principles
PHYSICS_SUBCATEGORIES = {
    # Mass properties (kg, lb)
    "mass": ["weight", "mass", "load", "payload"],
    
    # Dimensional properties (m, ft)
    "dimensions": ["height", "width", "length", "radius", "diameter", "size", "reach", "depth", "clearance"],
    
    # Force properties (N, lbf)
    "force": ["force", "strength", "pressure", "torque", "lift", "thrust", "traction"],
    
    # Power properties (W, hp)
    "power": ["power", "output", "consumption", "efficiency", "energy"],
    
    # Kinematic properties (velocity, acceleration)
    "kinematics": ["speed", "velocity", "acceleration", "rpm", "rotation", "frequency", "rate"],
    
    # Flow properties (volumetric flow rates)
    "flow": ["flow", "discharge", "volume_rate", "pump"],
    
    # Electrical properties
    "electrical": ["voltage", "current", "resistance", "electrical", "amp", "battery", "charge"],
    
    # Thermal properties
    "thermal": ["temperature", "heat", "thermal", "cooling"],
    
    # Acoustic properties
    "acoustic": ["noise", "sound", "acoustic", "decibel"],
    
    # Temporal properties
    "time": ["time", "duration", "period", "cycle", "interval"],
    
    # Volumetric properties
    "volume": ["volume", "capacity", "tank", "container"],
    
    # Default category if no match
    "general": []
}

# Define subcategories for brand attributes
BRAND_SUBCATEGORIES = {
    # Identification attributes
    "identification": ["model", "manufacturer", "brand", "name", "id", "number"],
    
    # Specification attributes (brand-specific)
    "specifications": ["type", "series", "configuration"],
    
    # Default category if no match
    "general": []
}

# Define canonical physics attributes and their common variations
CANONICAL_PHYSICS_ATTRIBUTES = {
    # Mass attributes
    "weight": ["weight", "mass"],
    
    # Dimensional attributes
    "length": ["length", "height", "width", "depth", "thickness"],
    "diameter": ["diameter", "radius"],
    "area": ["area", "surface"],
    
    # Force attributes
    "force": ["force", "strength", "impact"],
    "pressure": ["pressure", "psi", "bar"],
    "torque": ["torque", "moment"],
    
    # Power attributes
    "power": ["power", "output", "energy"],
    
    # Kinematic attributes
    "speed": ["speed", "velocity"],
    "rotation_speed": ["rpm", "rotation"],
    "acceleration": ["acceleration"],
    
    # Flow attributes
    "flow_rate": ["flow", "rate", "discharge"],
    
    # Electrical attributes
    "voltage": ["voltage", "volt"],
    "current": ["current", "ampere", "amp"],
    "frequency": ["frequency", "hertz", "hz"],
    "resistance": ["resistance", "ohm"],
    
    # Thermal attributes
    "temperature": ["temperature", "heat", "thermal"],
    
    # Acoustic attributes
    "noise_level": ["noise", "sound", "acoustic", "decibel"],
    
    # Temporal attributes
    "time": ["time", "duration", "period"],
    
    # Angular attributes
    "angle": ["angle", "degree", "rotation"],
    
    # Volumetric attributes
    "volume": ["volume", "capacity"]
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

# Standard units for physics attributes based on SI system
STANDARD_UNITS = {
    # Mass units
    "weight": "kg",
    
    # Dimensional units
    "length": "m",
    "diameter": "m",
    "area": "m²",
    
    # Force units
    "force": "N",
    "pressure": "Pa",
    "torque": "N·m",
    
    # Power units
    "power": "W",
    
    # Kinematic units
    "speed": "m/s",
    "rotation_speed": "rpm",
    "acceleration": "m/s²",
    
    # Flow units
    "flow_rate": "m³/s",
    
    # Electrical units
    "voltage": "V",
    "current": "A",
    "frequency": "Hz",
    "resistance": "Ω",
    
    # Thermal units
    "temperature": "°C",
    
    # Acoustic units
    "noise_level": "dB",
    
    # Temporal units
    "time": "s",
    
    # Angular units
    "angle": "°",
    
    # Volumetric units
    "volume": "m³"
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
                # Determine scientific subcategory
                subcategory = determine_subcategory(canonical)
                return canonical, subcategory
    
    # If no match found, return the cleaned attribute name and a general subcategory
    return normalized, "general"


def determine_subcategory(canonical_name: str) -> str:
    """
    Determine the scientific subcategory for a canonical physics attribute.
    
    Args:
        canonical_name: Canonical attribute name
        
    Returns:
        Scientific subcategory name
    """
    for subcategory, keywords in PHYSICS_SUBCATEGORIES.items():
        if subcategory == "general":
            continue
        
        # Check if canonical name or any part of it matches subcategory keywords
        for keyword in keywords:
            if keyword in canonical_name.lower():
                return subcategory
    
    # Map specific canonical names to their appropriate subcategories
    subcategory_map = {
        "weight": "mass",
        "length": "dimensions",
        "width": "dimensions",
        "height": "dimensions",
        "diameter": "dimensions",
        "force": "force",
        "pressure": "force",
        "torque": "force",
        "power": "power",
        "speed": "kinematics",
        "rotation_speed": "kinematics",
        "acceleration": "kinematics",
        "flow_rate": "flow",
        "voltage": "electrical",
        "current": "electrical",
        "temperature": "thermal",
        "noise_level": "acoustic",
        "time": "time",
        "angle": "dimensions",
        "volume": "volume"
    }
    
    return subcategory_map.get(canonical_name, "general")


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
