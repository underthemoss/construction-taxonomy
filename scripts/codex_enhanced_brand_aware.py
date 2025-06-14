#!/usr/bin/env python
"""
Brand-Aware Codex attribute proposer:
 u2022 Analyzes product content to identify potential attributes
 u2022 Distinguishes between brand-specific and physics-based attributes
 u2022 Applies strict schema validation and deduplication
 u2022 Creates a PR for human review
"""
import json, os, subprocess, datetime, pathlib, requests, openai, sys, re
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict

# Import physics attribute normalizer
try:
    from physics_normalizer import normalize_physics_attribute, get_standard_unit, is_scientific_attribute
except ImportError:
    # If module not found, try with explicit path
    sys.path.append(str(pathlib.Path(__file__).parent))
    try:
        from physics_normalizer import normalize_physics_attribute, get_standard_unit, is_scientific_attribute
    except ImportError:
        print("Warning: Could not import physics_normalizer. Using simplified normalization.")
        
        # Fallback implementations if module not available
        def normalize_physics_attribute(attr_name):
            return attr_name.lower().replace(' ', '_'), "general"
            
        def get_standard_unit(canonical_attr):
            return ""
            
        def is_scientific_attribute(attr_name):
            return True  # Assume all are scientific in fallback mode

# Support both openai <1 and >=1
try:
    from openai import OpenAI  # type: ignore
    _OPENAI_CLIENT = OpenAI()
    _USE_CLIENT = True
except ImportError:  # old sdk
    _USE_CLIENT = False

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Attribute directories and files
ATTR_DIR = ROOT / "attributes"
PHYSICS_DIR = ATTR_DIR / "physics"
BRAND_DIR = ATTR_DIR / "brand"
CONSOLIDATED_DIR = ATTR_DIR / "consolidated"
ATTR_FILE = CONSOLIDATED_DIR / "consolidated_attributes.json"

# Other paths
EXAMPLES_DIR = ROOT / "examples"
SCHEMA_DIR = ROOT / "schema"
CATALOGS_DIR = ROOT / "data" / "product_catalogs"
SOURCE_CONTENT_DIR = CATALOGS_DIR / "example_source_content" / "pages copy"
ATTR_SCHEMA_FILE = SCHEMA_DIR / "attribute.schema.json"
BRANCH = f"codex/attr-{datetime.date.today()}"

openai.api_key = os.getenv("OPENAI_API_KEY")

# Common manufacturer names to help identify brand-specific content
MANUFACTURER_KEYWORDS = [
    "Caterpillar", "CAT", "John Deere", "JLG", "Genie", "Bobcat", "Komatsu", 
    "Kubota", "Volvo", "Hitachi", "Liebherr", "Terex", "CASE", "Hyundai", 
    "Kobelco", "Doosan", "Takeuchi", "JCB", "New Holland", "Manitou", "Skyjack"
]

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

# Utility functions
def git(*args):
    subprocess.check_call(["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL)

def load_attributes() -> Dict[str, Any]:
    """Load the consolidated attributes file."""
    with ATTR_FILE.open() as f:
        return json.load(f)

def load_schema() -> Dict[str, Any]:
    """Load the attribute schema for validation."""
    with ATTR_SCHEMA_FILE.open() as f:
        return json.load(f)

def load_examples() -> List[Dict[str, Any]]:
    """Load all example products to analyze their attributes."""
    examples = []
    for file_path in EXAMPLES_DIR.glob("*.json"):
        with file_path.open() as f:
            try:
                example = json.load(f)
                examples.append(example)
            except json.JSONDecodeError:
                print(f"Error parsing {file_path}")
    return examples

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

def detect_manufacturer(content: str) -> Optional[str]:
    """Detect which manufacturer is mentioned in the content."""
    for manufacturer in MANUFACTURER_KEYWORDS:
        if re.search(r'\b' + re.escape(manufacturer) + r'\b', content, re.IGNORECASE):
            return manufacturer
    return None

def analyze_source_content() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Set[str]]]:
    """Analyze source content pages to extract potential attributes and track manufacturer presence."""
    potential_attributes = {}
    normalized_physics_attributes = {}  # Track normalized physics attributes
    manufacturer_attributes = defaultdict(set)  # Track which manufacturers have which attributes
    manufacturer_count = defaultdict(set)      # Count unique manufacturers for each attribute
    
    # Check if the source content directory exists
    if not SOURCE_CONTENT_DIR.exists():
        print(f"Source content directory not found: {SOURCE_CONTENT_DIR}")
        return {}, defaultdict(set)
    
    # Process each page file
    for file_path in SOURCE_CONTENT_DIR.glob("*.txt"):
        try:
            with file_path.open() as f:
                content = f.read()
                
            # Detect manufacturer for this content
            manufacturer = detect_manufacturer(content)
            
            # Extract potential attributes using patterns
            # Look for patterns like "Specification: Value" or "Parameter: Value"
            attribute_patterns = [
                # "Name: Value" pattern
                r'\b([A-Z][\w\s-]+(?:\([^)]+\))?)\s*:\s*([\w\d\.\s-]+)(?:\(([^)]+)\))?',
                # Bullet point pattern with * or • symbol
                r'[*•]\s*([A-Z][\w\s-]+(?:\([^)]+\))?)\s*:\s*([\w\d\.\s-]+)(?:\(([^)]+)\))?',
                # Table-like format
                r'\|\s*([A-Z][\w\s-]+(?:\([^)]+\))?)\s*\|\s*([\w\d\.\s-]+)(?:\(([^)]+)\))?\s*\|'
            ]
            
            for pattern in attribute_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if len(match) >= 2:
                        attr_name = match[0].strip()
                        attr_value = match[1].strip()
                        
                        # Skip very short or non-specific attributes
                        if len(attr_name) < 3 or attr_name.lower() in ['the', 'and', 'for', 'with']:
                            continue
                            
                        # Generate a key for this attribute
                        attr_key = re.sub(r'\W+', '_', attr_name.lower())
                        
                        # Detect unit if present (often in parentheses or after a value)
                        unit = None
                        
                        # First check if unit is in parentheses in the match
                        if len(match) > 2 and match[2]:
                            unit = match[2].strip()
                        else:
                            # Try to extract primary unit from the value (e.g., '67,500 lb (30,600 kg)' → 'lb')
                            unit_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*([a-zA-Z]+(?:\s[a-zA-Z]+)?)', attr_value)
                            unit = None
                            if len(match) > 2 and match[2]:
                                unit = match[2].strip()
                            elif unit_match:
                                unit = unit_match.group(2).strip()
                        
                        # Determine if this is a physics attribute
                        is_physics = is_scientific_attribute(attr_name)
                        
                        # Check for brand patterns
                        brand_patterns = ['model', 'series', 'brand', 'type', 'certification', 'standard', 'warranty']
                        for pattern in brand_patterns:
                            if pattern in attr_name.lower():
                                is_physics = False
                                break
                        
                        # Set category based on classification
                        category = "physics" if is_physics else "brand"
                        
                        # Apply physics normalization if needed
                        canonical_name = attr_key
                        if is_physics:
                            canonical_name, subcategory = normalize_physics_attribute(attr_name)
                            
                            # Direct mapping override for important physics concepts
                            # This ensures proper scientific classification even if the normalizer isn't updated
                            if "weight" in attr_name.lower() or "mass" in attr_name.lower():
                                subcategory = "mass"  # Weight is a mass property, not dimensional
                            elif any(dim in attr_name.lower() for dim in ["length", "height", "width", "diameter"]):
                                subcategory = "dimensions"
                            elif any(power in attr_name.lower() for power in ["power", "energy", "output"]):
                                subcategory = "power"
                            elif any(force in attr_name.lower() for force in ["force", "pressure", "torque"]):
                                subcategory = "force"
                        else:
                            subcategory = "general"
                            
                        # Create or update the attribute record
                        if attr_key not in potential_attributes:
                            potential_attributes[attr_key] = {
                                "name": attr_name.strip(),
                                "category": category,
                                "sources": [str(file_path)],
                                "count": 1
                            }
                            
                            # Set the subcategory for both physics and brand attributes
                            potential_attributes[attr_key]["subcategory"] = subcategory
                            
                            # Add unit if available
                            if unit:
                                potential_attributes[attr_key]["unit"] = unit.strip()
                        else:
                            # Update existing attribute
                            potential_attributes[attr_key]["count"] += 1
                            if str(file_path) not in potential_attributes[attr_key]["sources"]:
                                potential_attributes[attr_key]["sources"].append(str(file_path))
                        
                        # Track manufacturer association
                        if manufacturer:
                            manufacturer_attributes[attr_key].add(manufacturer)
                            manufacturer_count[attr_key].add(manufacturer)
        
        except Exception as e:
            print(f"Error processing source file {file_path}: {e}")
    
    # Post-process to confirm attribute categories based on manufacturer presence
    for attr_key, manufacturers in manufacturer_attributes.items():
        # If an attribute appears across multiple manufacturers (3+), it's more likely to be physics
        if attr_key in potential_attributes and len(manufacturers) >= 3:
            potential_attributes[attr_key]["category"] = "physics"
    
    return potential_attributes, manufacturer_attributes

def validate_attribute(attr_def: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate an attribute against the schema."""
    # Check required fields
    for required in schema.get("required", []):
        if required not in attr_def:
            return False, f"Missing required field: {required}"
    
    # Check property types
    for prop, value in attr_def.items():
        if prop not in schema.get("properties", {}):
            return False, f"Unknown property: {prop}"
        
        prop_schema = schema["properties"][prop]
        prop_type = prop_schema.get("type")
        
        # Type checking
        if prop_type == "string" and not isinstance(value, str):
            return False, f"Property {prop} must be a string"
        elif prop_type == "number" and not isinstance(value, (int, float)):
            return False, f"Property {prop} must be a number"
        
        # Enum validation
        if "enum" in prop_schema and value not in prop_schema["enum"]:
            return False, f"Property {prop} must be one of: {prop_schema['enum']}"
    
    return True, None

def analyze_examples(examples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Analyze example products to identify common attribute patterns."""
    attribute_occurrences = {}
    total_examples = len(examples)
    
    # Count occurrences of each attribute
    for example in examples:
        for attr in example.get("attributes", []):
            attr_name = attr.get("name")
            if not attr_name:
                continue
                
            attr_key = re.sub(r'\W+', '_', attr_name.lower())
            value = attr.get("value")
            unit = attr.get("unit", "")
            
            if attr_key not in attribute_occurrences:
                attribute_occurrences[attr_key] = {
                    "name": attr_name,
                    "count": 0,
                    "values": [],
                    "units": set()
                }
            
            attribute_occurrences[attr_key]["count"] += 1
            if value is not None:
                attribute_occurrences[attr_key]["values"].append(value)
            if unit:
                attribute_occurrences[attr_key]["units"].add(unit)
    
    # Calculate commonality and determine types
    common_attributes = {}
    for key, info in attribute_occurrences.items():
        commonality = (info["count"] / total_examples) * 100
        if commonality >= 60:  # Consider attributes present in at least 60% of examples
            # Infer type from values
            attr_type = "string"  # Default
            if info["values"]:
                if all(isinstance(v, (int, float)) for v in info["values"]):
                    attr_type = "number"
                elif all(isinstance(v, bool) for v in info["values"]):
                    attr_type = "boolean"
            
            # Infer category based on presence of units (physics attributes typically have units)
            category = "physics" if info["units"] else "brand"
            
            # Select most common unit if available
            unit = next(iter(info["units"])) if info["units"] else None
            
            common_attributes[key] = {
                "name": info["name"],
                "type": attr_type,
                "category": category
            }
            
            if unit:
                common_attributes[key]["unit"] = unit
    
    return common_attributes

def deduplicate_attributes(new_attrs: Dict[str, Any], current_attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Remove any attributes that are semantically duplicates of existing ones."""
    deduped = {}
    
    # Helper function to normalize attribute name for comparison
    def normalize(name):
        return re.sub(r'\W+', '', name.lower())
    
    # Create a set of normalized existing attribute names
    existing_normalized = {normalize(attr["name"]) for attr in current_attrs.values()}
    
    # Check each new attribute
    for key, attr in new_attrs.items():
        # Skip if name is too similar to existing
        norm_name = normalize(attr["name"])
        if norm_name in existing_normalized:
            print(f"Skipping {attr['name']} as it appears to be a duplicate")
            continue
            
        # Skip if key already exists
        if key in current_attrs:
            print(f"Skipping {key} as this key already exists")
            continue
            
        deduped[key] = attr
    
    return deduped

def ask_codex(current_attrs: Dict[str, Any], catalog_attrs: Dict[str, Dict[str, Any]], example_attrs: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Ask Codex for improved attribute definitions based on analysis.
    
    Uses a scientific approach to physics attributes, treating them as pure physical properties
    without product-specific qualifiers."""
    prompt = (
        "You are an expert in construction equipment taxonomy and physics. \n\n"
        "ATTRIBUTE LIBRARY MODEL:\n"
        "We maintain a standardized attribute library with the following characteristics:\n"
        "1. Each attribute has a unique snake_case identifier (e.g., 'weight', 'length', 'voltage')\n"
        "2. Physics attributes MUST be pure scientific properties WITHOUT product qualifiers:\n"
        "   - GOOD: 'weight' (pure physical property)\n"
        "   - BAD: 'tool_weight' (contains product qualifier 'tool')\n"
        "3. Attributes are categorized as either 'physics' (universal physical properties) or 'brand' (manufacturer-specific)\n"
        "4. Products reference these standardized attributes instead of defining new ones\n\n"
        "PHYSICS ATTRIBUTE GUIDELINES:\n"
        "- Must be fundamental physical properties (mass, length, time, temperature, etc.)\n"
        "- Must NOT include product-specific qualifiers (engine_, tool_, battery_, etc.)\n"
        "- Must use standard scientific units (kg, m, s, °C, etc.)\n"
        "- Names should be canonical (e.g., 'weight' not 'mass_of_tool')\n\n"
        "PRODUCT CATALOG EXAMPLE:\n"
        "```\n"
        "* Operating Weight: 67,500 lb (30,600 kg)\n"
        "* Engine Model: Cat C7.1 ACERT\n"
        "* Net Power: 204 hp (152 kW)\n"
        "* Maximum Dig Depth: 24 ft 1 in (7.34 m)\n"
        "* Maximum Reach at Ground Level: 35 ft 10 in (10.92 m)\n"
        "```\n\n"
        "Below are three sets of attributes:\n"
        "1. CURRENT ATTRIBUTES in our taxonomy library:\n"
        f"{json.dumps(current_attrs, indent=2)}\n\n"
        "2. CATALOG ATTRIBUTES extracted from manufacturer catalogs:\n"
        f"{json.dumps(catalog_attrs, indent=2)}\n\n"
        "3. EXAMPLE ATTRIBUTES identified from product examples:\n"
        f"{json.dumps(example_attrs, indent=2)}\n\n"
        "4. ATTRIBUTE SCHEMA that all attributes must follow:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Based on this information:\n"
        "1. Identify 3-5 NEW attributes that aren't in the current library but would be valuable additions\n"
        "2. CAREFULLY distinguish between PHYSICS attributes (common across manufacturers) and BRAND attributes\n"
        "3. Focus on attributes commonly found in product specifications\n"
        "4. Each attribute must follow the schema exactly\n"
        "5. Provide snake_case keys and proper categorization\n\n"
        "Return EXACTLY a JSON object with this structure:\n"
        "{\"new_attributes\": {\"attribute_key\": {attribute definition}, ...}}\n\n"
        "Note: Each attribute definition must include name, type, category, and unit (if applicable)."
    )
    
    # Call OpenAI API
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    if _USE_CLIENT:
        rsp = _OPENAI_CLIENT.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert taxonomy curator for construction equipment. You understand the distinction between brand-specific and physics-based attributes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        content = rsp.choices[0].message.content
    else:
        rsp = openai.ChatCompletion.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert taxonomy curator for construction equipment. You understand the distinction between brand-specific and physics-based attributes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        content = rsp.choices[0].message.content
    
    # Parse and validate response
    try:
        raw = content.strip()
        # Remove markdown fences if present (```json ... ```)
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z0-9]*\n", "", raw)  # drop opening fence
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        parsed = json.loads(raw)
        return parsed.get("new_attributes", {})
    except Exception as e:
        print(f"Error parsing Codex response: {e}")
        print(f"Raw response: {raw[:500]}...")
        return {}

def main():
    # Set up branch
    git("fetch", "origin")
    git("checkout", "-B", BRANCH)
    
    # Load existing data
    attrs_data = load_attributes()
    current_attrs = attrs_data.get("attributes", {})
    schema = load_schema()
    
    # Load and analyze examples
    print("Analyzing example products...")
    examples = load_examples()
    example_attrs = analyze_examples(examples)
    print(f"Found {len(example_attrs)} potential attributes from examples")
    
    # Load and analyze source content with manufacturer awareness
    print("Analyzing source content with brand awareness...")
    content_attrs, manufacturer_data = analyze_source_content()
    # Print stats about the extracted attributes
    total_attrs = len(content_attrs)
    physics_attrs = len([a for a in content_attrs.values() if a.get("category") == "physics"])
    brand_attrs = len([a for a in content_attrs.values() if a.get("category") == "brand"])
    common_attrs = len([a for a, manufacturers in manufacturer_data.items() if len(manufacturers) > 1])
    
    print(f"Found {total_attrs} potential attributes from source content")
    print(f"  Physics attributes: {physics_attrs}")
    print(f"  Brand attributes: {brand_attrs}")
    print(f"  Attributes appearing across multiple manufacturers: {common_attrs}")
    
    # Use different filtering criteria for physics vs. brand attributes
    filtered_attributes = {}
    
    # For physics attributes: Accept any with valid units, regardless of manufacturer count
    # For brand attributes: Require multiple manufacturer mentions for validation
    for attr_key, attr_data in content_attrs.items():
        category = attr_data.get("category", "")
        
        # Physics attributes just need to be physically meaningful
        if category == "physics":
            # Accept physics attributes without manufacturer restrictions
            filtered_attributes[attr_key] = attr_data
        else:
            # Brand attributes need validation across manufacturers
            manufacturers = manufacturer_data.get(attr_key, set())
            if len(manufacturers) > 1:
                filtered_attributes[attr_key] = attr_data
    
    # Ask Codex for suggestions based on analysis with brand awareness
    print("Consulting Codex for attribute recommendations...")
    suggested_attrs = ask_codex(current_attrs, filtered_attributes, example_attrs, schema)
    print(f"Codex suggested {len(suggested_attrs)} new attributes")
    
    # Deduplicate and validate
    deduped_attrs = deduplicate_attributes(suggested_attrs, current_attrs)
    print(f"After deduplication: {len(deduped_attrs)} attributes remain")
    
    # Validate against schema
    valid_attrs = {}
    for key, attr in deduped_attrs.items():
        is_valid, error = validate_attribute(attr, schema)
        if is_valid:
            valid_attrs[key] = attr
        else:
            print(f"Attribute {key} failed validation: {error}")
    
    print(f"After validation: {len(valid_attrs)} attributes remain")
    
    # If no valid attributes, exit
    if not valid_attrs:
        print("No valid new attributes to add.")
        return
    
    # Create individual attribute files in the appropriate directories
    today = datetime.date.today().isoformat()
    created_files = []
    
    for attr_code, attr_data in valid_attrs.items():
        # Get category and determine subcategory
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
            dest_dir = PHYSICS_DIR / subcategory
        else:  # brand
            dest_dir = BRAND_DIR / subcategory
        
        # Ensure directory exists
        dest_dir.mkdir(exist_ok=True, parents=True)
        
        # Write the individual attribute file
        dest_file = dest_dir / f"{attr_code}.json"
        with open(dest_file, 'w') as f:
            json.dump(complete_attr, f, indent=2)
        
        created_files.append(dest_file)
        print(f"Created {dest_file}")
    
    # Run the consolidation script to update the consolidated file
    try:
        consolidate_script = ROOT / "scripts" / "consolidate_attributes.py"
        if consolidate_script.exists():
            subprocess.check_call(["python", str(consolidate_script)], cwd=ROOT)
            print("Consolidated attribute file updated.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to run consolidation script: {e}")
    
    # Validate entire repo
    try:
        subprocess.check_call(["python", "scripts/validate.py"], cwd=ROOT)
        print("Validation successful!")
    except subprocess.CalledProcessError:
        print("Validation failed. Rolling back changes.")
        for file in created_files:
            if file.exists():
                file.unlink()
        return
    
    # Ensure git identity (needed in CI containers)
    git("config", "user.email", "codex-bot@users.noreply.github.com")
    git("config", "user.name", "codex-bot")

    # Commit and push changes
    git("add", str(ATTR_FILE))
    git("commit", "-m", f"feat(codex): add attributes {', '.join(valid_attrs.keys())}")
    
    # Handle GitHub token for authentication
    gh_token = os.getenv("GITHUB_TOKEN")
    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    
    # Get token from helper if in CI and no direct token
    if is_ci and not gh_token and os.path.exists(pathlib.Path(__file__).with_name("get_installation_token.py")):
        try:
            helper = pathlib.Path(__file__).with_name("get_installation_token.py")
            gh_token = subprocess.check_output(
                ["python", str(helper)],
                env=os.environ,
                text=True
            ).strip()
            print("Retrieved token from helper script")
        except Exception as e:
            print(f"Could not get token from helper: {e}")
    
    # Push changes
    if gh_token:
        # Use token for auth
        repo = os.getenv("GITHUB_REPOSITORY", "underthemoss/construction-taxonomy")
        remote_url = f"https://x-access-token:{gh_token}@github.com/{repo}.git"
        git("push", "-f", remote_url, BRANCH)
    elif not is_ci:
        # Only try pushing without token if not in CI
        git("push", "-f", "origin", BRANCH)
    else:
        print("⚠️ Skipping git push in CI environment without token")
    
    # Create or update PR
    repo = os.getenv("GITHUB_REPOSITORY", "underthemoss/construction-taxonomy")
    
    # Skip PR creation if no token
    if not gh_token:
        print("⚠️ No GitHub token available, skipping PR creation")
        return
    
    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github+json"
    }
    
    api = f"https://api.github.com/repos/{repo}"
    prs = requests.get(f"{api}/pulls?head={repo.split('/')[0]}:{BRANCH}",
                       headers=headers, timeout=20).json()
    
    if prs:
        print("PR already exists; branch just force-pushed.")
        return
    
    # Format PR details with category and subcategory information
    physics_attrs_by_subcategory = {}
    brand_attrs_by_subcategory = {}
    
    # Initialize subcategory lists
    for subcategory in PHYSICS_SUBCATEGORIES.keys():
        physics_attrs_by_subcategory[subcategory] = []
    for subcategory in BRAND_SUBCATEGORIES.keys():
        brand_attrs_by_subcategory[subcategory] = []
    
    for key, attr in valid_attrs.items():
        category = attr.get("category", "")
        subcategory = determine_subcategory(key, attr, category)
        
        detail = f"* `{key}`: {attr['name']} ({attr['type']}"
        if "unit" in attr:
            detail += f", {attr['unit']}"
        detail += ")" 
        
        if category == "physics":
            physics_attrs_by_subcategory[subcategory].append(detail)
        else:
            brand_attrs_by_subcategory[subcategory].append(detail)
    
    # Create the PR body with categorized attributes by subcategory
    body = (
        "### Codex Attribute Proposal\n\n"
        "Automated PR adding new attribute definitions suggested by Codex.\n\n"
        "## New Physics Attributes:\n"
    )
    
    # Add physics attributes by subcategory
    physics_count = 0
    for subcategory, attrs in physics_attrs_by_subcategory.items():
        if attrs:
            physics_count += len(attrs)
            body += f"\n### {subcategory.title()}:\n"
            body += "\n".join(attrs) + "\n"
    
    if physics_count == 0:
        body += "\nNone\n"
    
    body += "\n## New Brand Attributes:\n"
    
    # Add brand attributes by subcategory
    brand_count = 0
    for subcategory, attrs in brand_attrs_by_subcategory.items():
        if attrs:
            brand_count += len(attrs)
            body += f"\n### {subcategory.title()}:\n"
            body += "\n".join(attrs) + "\n"
    
    if brand_count == 0:
        body += "\nNone\n"
        
    body += "\n"
        
    body += (
        "#### Analysis Process:\n"
        "- Analyzed existing attributes and product examples\n"
        "- Extracted potential attributes from source content with brand awareness\n"
        "- Applied strict schema validation\n"
        "- Removed potential duplicates\n"
        "- Verified attribute commonality across products\n"
        "- Separated physics and brand attributes\n\n"
        "- [ ] Human review required (>=1 CODEOWNER)\n"
        "- Source: LLM (Codex)\n"
    )
    
    # Create PR
    # Count was already calculated in PR body generation
    requests.post(
        f"{api}/pulls",
        headers=headers,
        json={
            "title": f"feat: Add {physics_count} physics and {brand_count} brand attributes via Codex",
            "head": BRANCH,
            "base": "main",
            "body": body,
            "maintainer_can_modify": True
        },
        timeout=20
    )
    
    print(f"Successfully created PR with {len(valid_attrs)} new attributes!")

if __name__ == "__main__":
    main()
