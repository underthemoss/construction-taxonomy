#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path
import jsonschema
from jsonschema import validate

# Root directory of the repository
ROOT_DIR = Path(__file__).parent.parent.absolute()

# Schema directories
SCHEMA_DIR = ROOT_DIR / "schema"

# Data directories
ATTRIBUTES_DIR = ROOT_DIR / "attributes"
CATEGORIES_DIR = ROOT_DIR / "categories"
EXAMPLES_DIR = ROOT_DIR / "examples"

# Load schemas
def load_schema(schema_file):
    schema_path = SCHEMA_DIR / schema_file
    with open(schema_path, 'r') as f:
        return json.load(f)

# Validate JSON file against a schema
def validate_json_file(file_path, schema):
    with open(file_path, 'r') as f:
        try:
            data = json.load(f)
            validate(instance=data, schema=schema)
            return True
        except json.JSONDecodeError as e:
            print(f"Error parsing {file_path}: {e}")
            return False
        except jsonschema.exceptions.ValidationError as e:
            print(f"Validation error in {file_path}: {e}")
            return False

# Validate attribute files
def validate_attributes():
    schema = load_schema("attribute.schema.json")
    success = True
    
    for file_path in ATTRIBUTES_DIR.glob("*.json"):
        success = validate_json_file(file_path, schema) and success
    
    return success

# Validate category files
def validate_categories():
    schema = load_schema("category.schema.json")
    success = True
    
    for file_path in CATEGORIES_DIR.glob("*.json"):
        success = validate_json_file(file_path, schema) and success
    
    return success

# Validate product examples
def validate_examples():
    schema = load_schema("product.schema.json")
    success = True
    
    for file_path in EXAMPLES_DIR.glob("*.json"):
        success = validate_json_file(file_path, schema) and success
    
    return success

# Main function
def main():
    print("Validating taxonomy data...")
    
    # Validate all files
    attr_valid = validate_attributes()
    cat_valid = validate_categories()
    ex_valid = validate_examples()
    
    # Print results
    print(f"\nValidation results:")
    print(f"Attributes: {'✓' if attr_valid else '✗'}")
    print(f"Categories: {'✓' if cat_valid else '✗'}")
    print(f"Examples: {'✓' if ex_valid else '✗'}")
    
    # Exit with appropriate code
    if attr_valid and cat_valid and ex_valid:
        print("\nAll files are valid!")
        return 0
    else:
        print("\nValidation failed. Please fix the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
