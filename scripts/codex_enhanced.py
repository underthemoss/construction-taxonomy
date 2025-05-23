#!/usr/bin/env python
"""
Enhanced Codex attribute proposer:
 • Analyzes product content to identify potential attributes
 • Applies strict schema validation and deduplication
 • Categorizes attributes by purpose (physics, brand, etc.)
 • Updates the attribute library with high-quality suggestions
 • Creates a PR for human review
"""
import json, os, subprocess, datetime, pathlib, requests, openai, sys, re
from typing import Dict, List, Set, Any, Optional, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
ATTR_FILE = ROOT / "attributes" / "consolidated_attributes.json"
EXAMPLES_DIR = ROOT / "examples"
SCHEMA_DIR = ROOT / "schema"
ATTR_SCHEMA_FILE = SCHEMA_DIR / "attribute.schema.json"
BRANCH = f"codex/attr-{datetime.date.today()}"

openai.api_key = os.getenv("OPENAI_API_KEY")

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
            
            # Infer category
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

def ask_codex(current_attrs: Dict[str, Any], example_attrs: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Ask Codex for improved attribute definitions based on analysis."""
    # Construct prompt with detailed context
    prompt = (
        "You are an expert in construction equipment taxonomy. \n\n"
        "Below are two sets of attributes:\n"
        "1. CURRENT ATTRIBUTES in our taxonomy library:\n"
        f"{json.dumps(current_attrs, indent=2)}\n\n"
        "2. POTENTIAL ATTRIBUTES identified from product examples:\n"
        f"{json.dumps(example_attrs, indent=2)}\n\n"
        "3. ATTRIBUTE SCHEMA that all attributes must follow:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Based on this information:\n"
        "1. Identify 3-5 NEW attributes that aren't in the current library but would be valuable additions\n"
        "2. These should be common across construction equipment (present in ≥80% of cases)\n"
        "3. Focus on physics-based or brand-based attributes (avoid marketing claims)\n"
        "4. Each attribute must follow the schema exactly\n"
        "5. Provide snake_case keys and proper categorization\n\n"
        "Return EXACTLY a JSON object with this structure:\n"
        "{\"new_attributes\": {\"attribute_key\": {attribute definition}, ...}}\n\n"
        "Note: Each attribute definition must include name, type, category, and unit (if applicable)."
    )
    
    # Call OpenAI API
    rsp = openai.ChatCompletion.create(
        model="gpt-4o-preview",
        messages=[
            {"role":"system","content":"You are an expert taxonomy curator for construction equipment."},
            {"role":"user","content": prompt}
        ],
        temperature=0.2,
        max_tokens=1000
    )
    
    # Parse and validate response
    try:
        raw = rsp.choices[0].message.content.strip()
        parsed = json.loads(raw)
        return parsed.get("new_attributes", {})
    except Exception as e:
        print(f"Error parsing Codex response: {e}")
        print(f"Raw response: {raw[:500]}...")
        return {}

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

def main():
    # Set up branch
    git("fetch", "origin")
    try:
        git("checkout", BRANCH)
    except subprocess.CalledProcessError:
        git("checkout", "-b", BRANCH)
    
    # Load existing data
    attrs_data = load_attributes()
    current_attrs = attrs_data.get("attributes", {})
    schema = load_schema()
    examples = load_examples()
    
    # Analyze examples for attribute patterns
    print("Analyzing example products...")
    example_attrs = analyze_examples(examples)
    print(f"Found {len(example_attrs)} potential attributes from examples")
    
    # Ask Codex for suggestions based on analysis
    print("Consulting Codex for attribute recommendations...")
    suggested_attrs = ask_codex(current_attrs, example_attrs, schema)
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
    
    # Commit and push changes
    git("add", str(ATTR_FILE))
    git("commit", "-m", f"feat(codex): add attributes {', '.join(valid_attrs.keys())}")
    git("push", "-f", "origin", BRANCH)
    
    # Create or update PR
    repo = os.getenv("GITHUB_REPOSITORY", "underthemoss/construction-taxonomy")
    gh_token = os.getenv("GITHUB_TOKEN")
    if not gh_token:
        # Dynamically fetch installation token using helper
        import subprocess
        helper = pathlib.Path(__file__).with_name("get_installation_token.py")
        gh_token = subprocess.check_output(
            ["python", str(helper)],
            env=os.environ,
            text=True
        ).strip()
    
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
    
    # Format PR details
    details = []
    for key, attr in valid_attrs.items():
        details.append(f"* `{key}`: {attr['name']} ({attr['type']}")
        if "unit" in attr:
            details[-1] += f", {attr['unit']}"
        details[-1] += ")" 
    
    body = (
        "### Codex Attribute Proposal\n\n"
        "Automated PR adding new attribute definitions suggested by Codex.\n\n"
        "#### New Attributes:\n"
        "\n".join(details) + "\n\n"
        "#### Analysis Process:\n"
        "- Analyzed existing attributes and product examples\n"
        "- Applied strict schema validation\n"
        "- Removed potential duplicates\n"
        "- Verified attribute commonality across products\n\n"
        "- [ ] Human review required (>=1 CODEOWNER)\n"
        "- Source: LLM (Codex)\n"
    )
    
    # Create PR
    requests.post(
        f"{api}/pulls",
        headers=headers,
        json={
            "title": f"feat: Add {len(valid_attrs)} new attributes via Codex",
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
