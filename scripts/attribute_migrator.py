#!/usr/bin/env python
"""
Attribute Migration Script

Migrates attributes from flat structure to hierarchical directory structure
with individual files for each attribute.

Run this script from the root of the repository:
  python scripts/attribute_migrator.py
"""

import json
import os
import shutil
import datetime
from pathlib import Path

# Define the repository root and attributes paths
ROOT = Path(__file__).resolve().parents[1]
ATTR_DIR = ROOT / "attributes"
CONSOLIDATED_FILE = ATTR_DIR / "consolidated_attributes.json"

# Define the new directory structure
NEW_PHYSICS_DIR = ATTR_DIR / "physics"
NEW_BRAND_DIR = ATTR_DIR / "brand"
NEW_CONSOLIDATED_DIR = ATTR_DIR / "consolidated"

# Define subcategories for physics attributes
PHYSICS_SUBCATEGORIES = {
    # Dimensions and size-related attributes
    "dimensions": ["height", "width", "length", "radius", "platform", "size", "capacity", "weight"],
    
    # Performance-related attributes
    "performance": ["speed", "power", "flow", "rate", "efficiency", "capacity", "range", "level"],
    
    # Electrical attributes
    "electrical": ["voltage", "battery", "current", "electrical", "amp"],
    
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


def determine_subcategory(attr_code, attr_data, category):
    """Determine the appropriate subcategory for an attribute."""
    if category == "physics":
        subcategories = PHYSICS_SUBCATEGORIES
    else:  # brand
        subcategories = BRAND_SUBCATEGORIES
    
    # Check each subcategory's keywords for a match in the attribute code
    for subcategory, keywords in subcategories.items():
        if subcategory == "general":
            continue
            
        for keyword in keywords:
            if keyword in attr_code.lower():
                return subcategory
    
    # Default to general if no match found
    return "general"


def create_directory_structure():
    """Create the new directory structure."""
    # Create base directories
    NEW_PHYSICS_DIR.mkdir(exist_ok=True)
    NEW_BRAND_DIR.mkdir(exist_ok=True)
    NEW_CONSOLIDATED_DIR.mkdir(exist_ok=True)
    
    # Create physics subcategories
    for subcategory in PHYSICS_SUBCATEGORIES.keys():
        (NEW_PHYSICS_DIR / subcategory).mkdir(exist_ok=True)
    
    # Create brand subcategories
    for subcategory in BRAND_SUBCATEGORIES.keys():
        (NEW_BRAND_DIR / subcategory).mkdir(exist_ok=True)


def migrate_attributes():
    """Migrate attributes from the consolidated file to individual files."""
    # Load the consolidated attributes file
    with open(CONSOLIDATED_FILE, 'r') as f:
        data = json.load(f)
    
    attributes = data.get("attributes", {})
    today = datetime.date.today().isoformat()
    
    # Process each attribute
    for attr_code, attr_data in attributes.items():
        category = attr_data.get("category", "physics")
        subcategory = determine_subcategory(attr_code, attr_data, category)
        
        # Create the complete attribute data with additional metadata
        complete_attr = {
            "code": attr_code,
            "name": attr_data.get("name", ""),
            "type": attr_data.get("type", ""),
            "category": category,
            "subcategory": subcategory,
            "added_date": today,
            "last_modified": today
        }
        
        # Add optional fields if they exist
        if "unit" in attr_data:
            complete_attr["unit"] = attr_data["unit"]
        if "description" in attr_data:
            complete_attr["description"] = attr_data["description"]
        
        # Determine the destination path
        if category == "physics":
            dest_dir = NEW_PHYSICS_DIR / subcategory
        else:  # brand
            dest_dir = NEW_BRAND_DIR / subcategory
        
        # Write the individual attribute file
        dest_file = dest_dir / f"{attr_code}.json"
        with open(dest_file, 'w') as f:
            json.dump(complete_attr, f, indent=2)
        
        print(f"Created {dest_file}")


def backup_existing_files():
    """Backup existing attribute files."""
    backup_dir = ATTR_DIR / "backup"
    backup_dir.mkdir(exist_ok=True)
    
    # Copy the consolidated file
    if CONSOLIDATED_FILE.exists():
        shutil.copy2(CONSOLIDATED_FILE, backup_dir / "consolidated_attributes.json")
    
    # Copy any individual attribute files
    for attr_file in ATTR_DIR.glob("*.json"):
        if attr_file.name != "consolidated_attributes.json":
            shutil.copy2(attr_file, backup_dir / attr_file.name)
    
    print(f"Backed up existing files to {backup_dir}")


def main():
    """Main function to run the migration."""
    print("Starting attribute migration...")
    
    # Backup existing files
    backup_existing_files()
    
    # Create the new directory structure
    create_directory_structure()
    
    # Migrate the attributes
    migrate_attributes()
    
    # Success message
    print("\nMigration complete!")


if __name__ == "__main__":
    main()
