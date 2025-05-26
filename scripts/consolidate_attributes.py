#!/usr/bin/env python
"""
Attribute Consolidation Script

Consolidates individual attribute files into a single consolidated JSON file.

Run this script from the root of the repository:
  python scripts/consolidate_attributes.py
"""

import json
import os
from pathlib import Path

# Define the repository root and attributes paths
ROOT = Path(__file__).resolve().parents[1]
ATTR_DIR = ROOT / "attributes"
NEW_PHYSICS_DIR = ATTR_DIR / "physics"
NEW_BRAND_DIR = ATTR_DIR / "brand"
CONSOLIDATED_DIR = ATTR_DIR / "consolidated"
CONSOLIDATED_FILE = CONSOLIDATED_DIR / "consolidated_attributes.json"

def consolidate_attributes():
    """Consolidate individual attribute files into a single file."""
    consolidated = {"attributes": {}}
    
    # Process physics attributes
    for subdir in NEW_PHYSICS_DIR.iterdir():
        if subdir.is_dir():
            for attr_file in subdir.glob("*.json"):
                with open(attr_file, 'r') as f:
                    attr_data = json.load(f)
                
                # Extract the core attribute data for consolidated file
                attr_code = attr_data["code"]
                consolidated_attr = {
                    "name": attr_data["name"],
                    "type": attr_data["type"],
                    "category": attr_data["category"]
                }
                
                # Add optional fields
                if "unit" in attr_data:
                    consolidated_attr["unit"] = attr_data["unit"]
                if "description" in attr_data:
                    consolidated_attr["description"] = attr_data["description"]
                
                consolidated["attributes"][attr_code] = consolidated_attr
    
    # Process brand attributes
    for subdir in NEW_BRAND_DIR.iterdir():
        if subdir.is_dir():
            for attr_file in subdir.glob("*.json"):
                with open(attr_file, 'r') as f:
                    attr_data = json.load(f)
                
                # Extract the core attribute data for consolidated file
                attr_code = attr_data["code"]
                consolidated_attr = {
                    "name": attr_data["name"],
                    "type": attr_data["type"],
                    "category": attr_data["category"]
                }
                
                # Add optional fields
                if "unit" in attr_data:
                    consolidated_attr["unit"] = attr_data["unit"]
                if "description" in attr_data:
                    consolidated_attr["description"] = attr_data["description"]
                
                consolidated["attributes"][attr_code] = consolidated_attr
    
    # Write the consolidated file
    with open(CONSOLIDATED_FILE, 'w') as f:
        json.dump(consolidated, f, indent=2)
    
    print(f"Created consolidated file with {len(consolidated['attributes'])} attributes")

if __name__ == "__main__":
    consolidate_attributes()
