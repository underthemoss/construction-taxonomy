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

# Support both openai <1 and >=1
try:
    from openai import OpenAI  # type: ignore
    _OPENAI_CLIENT = OpenAI()
    _USE_CLIENT = True
except ImportError:  # old sdk
    _USE_CLIENT = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
ATTR_FILE = ROOT / "attributes" / "consolidated_attributes.json"
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

def detect_manufacturer(content: str) -> Optional[str]:
    """Detect which manufacturer is mentioned in the content."""
    for manufacturer in MANUFACTURER_KEYWORDS:
        if re.search(r'\b' + re.escape(manufacturer) + r'\b', content, re.IGNORECASE):
            return manufacturer
    return None

def analyze_source_content() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Set[str]]]:
    """Analyze source content pages to extract potential attributes and track manufacturer presence."""
    potential_attributes = {}
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
                            if unit_match:
                                unit = unit_match.group(2).strip()
                            
                            # Look for dual units in parentheses
                            dual_unit_match = re.search(r'\((\d+(?:[,\.]\d+)?)\s*([a-zA-Z]+(?:\s[a-zA-Z]+)?)', attr_value)
                            # If we have dual units but no primary unit, use the secondary unit
                            if dual_unit_match and not unit:
                                unit = dual_unit_match.group(2).strip()
                        
                        # Determine if this is a physics or brand attribute
                        # Physics attributes typically have units and numeric values
                        is_physics = False
                        if unit or re.search(r'\d+(?:\.\d+)?', attr_value):
                            is_physics = True
                        
                        # Store the attribute
                        if attr_key not in potential_attributes:
                            potential_attributes[attr_key] = {
                                "name": attr_name,
                                "type": "number" if is_physics else "string",
                                "category": "physics" if is_physics else "brand",
                            }
                            
                            if unit:
                                potential_attributes[attr_key]["unit"] = unit
                        
                        # Track which manufacturer has this attribute
                        if manufacturer:
                            manufacturer_attributes[attr_key].add(manufacturer)
                        
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

def ask_codex(current_attrs: Dict[str, Any], catalog_attrs: Dict[str, Dict[str, Any]], example_attrs: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Ask Codex for improved attribute definitions based on analysis."""
    prompt = (
        "You are an expert in construction equipment taxonomy. \n\n"
        "ATTRIBUTE LIBRARY MODEL:\n"
        "Our construction taxonomy uses a centralized attribute library where:\n"
        "1. Each attribute has a unique snake_case identifier (e.g., 'max_platform_height')\n"
        "2. Attributes are categorized as either 'physics' (properties shared across manufacturers) or 'brand' (manufacturer-specific)\n"
        "3. Products reference these standardized attributes instead of defining new ones\n\n"
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
    print(f"Found {len(content_attrs)} potential attributes from source content")
    
    # Count attributes by category
    physics_count = sum(1 for attr in content_attrs.values() if attr.get("category") == "physics")
    brand_count = sum(1 for attr in content_attrs.values() if attr.get("category") == "brand")
    print(f"  Physics attributes: {physics_count}")
    print(f"  Brand attributes: {brand_count}")
    
    # Count cross-manufacturer attributes
    cross_manufacturer = sum(1 for key, manufacturers in manufacturer_data.items() if len(manufacturers) > 1)
    print(f"  Attributes appearing across multiple manufacturers: {cross_manufacturer}")
    
    # Ask Codex for suggestions based on analysis with brand awareness
    print("Consulting Codex for attribute recommendations...")
    suggested_attrs = ask_codex(current_attrs, content_attrs, example_attrs, schema)
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
    
    # Update attributes file
    attrs_data["attributes"].update(valid_attrs)
    with ATTR_FILE.open("w") as f:
        json.dump(attrs_data, f, indent=2)
    
    # Validate entire repo
    try:
        subprocess.check_call(["python", "scripts/validate.py"], cwd=ROOT)
        print("Validation successful!")
    except subprocess.CalledProcessError:
        print("Validation failed. Rolling back changes.")
        git("checkout", "--", str(ATTR_FILE))
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
    
    # Format PR details with category information
    physics_attrs = []
    brand_attrs = []
    
    for key, attr in valid_attrs.items():
        category = attr.get("category", "")
        detail = f"* `{key}`: {attr['name']} ({attr['type']}"
        if "unit" in attr:
            detail += f", {attr['unit']}"
        detail += ")" 
        
        if category == "physics":
            physics_attrs.append(detail)
        else:
            brand_attrs.append(detail)
    
    # Create the PR body with separated physics and brand attributes
    body = (
        "### Codex Attribute Proposal\n\n"
        "Automated PR adding new attribute definitions suggested by Codex.\n\n"
        "#### New Physics Attributes:\n"
    )
    
    if physics_attrs:
        body += "\n".join(physics_attrs) + "\n\n"
    else:
        body += "None\n\n"
        
    body += (
        "#### New Brand Attributes:\n"
    )
    
    if brand_attrs:
        body += "\n".join(brand_attrs) + "\n\n"
    else:
        body += "None\n\n"
        
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
    physics_count = len(physics_attrs)
    brand_count = len(brand_attrs)
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
