#!/usr/bin/env python
"""
Attribute Migration Script

Migrates attributes from flat structure to hierarchical directory structure
with individual files for each attribute.

Run this script from the root of the repository:
  python scripts/migrate_attributes.py
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


def create_consolidation_script():
    """Create a script to consolidate individual attribute files."""
    script_content = """#!/usr/bin/env python
"""Attribute Consolidation Script

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
"""
    
    # Write the consolidation script
    script_path = ROOT / "scripts" / "consolidate_attributes.py"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make it executable
    os.chmod(script_path, 0o755)
    print(f"Created consolidation script at {script_path}")


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


def update_scripts():
    """Update the scripts to work with the new structure."""
    # Create a sample update to codex_populate.py
    update_note = """
# TODO: Update the following scripts to use the new attribute structure:
# 1. scripts/codex_populate.py
#    - Update `ATTR_FILE` to use consolidated/consolidated_attributes.json
#    - Modify attribute creation to write individual files

# 2. scripts/codex_enhanced_brand_aware.py
#    - Update `ATTR_FILE` to use consolidated/consolidated_attributes.json
#    - Modify attribute creation to write individual files

# 3. scripts/validate.py
#    - Update validation to check both individual files and consolidated file
"""
    
    print(update_note)


def main():
    """Main function to run the migration."""
    print("Starting attribute migration...")
    
    # Backup existing files
    backup_existing_files()
    
    # Create the new directory structure
    create_directory_structure()
    
    # Migrate the attributes
    migrate_attributes()
    
    # Create the consolidation script
    create_consolidation_script()
    
    # Note about updating scripts
    update_scripts()
    
    print("\nMigration complete! Run the consolidation script to generate the consolidated file:")
    print("  python scripts/consolidate_attributes.py")


if __name__ == "__main__":
    main()
