#!/usr/bin/env python
"""
Codex attribute proposer:
 • Reads attributes/attributes.json
 • Asks Codex for 1-5 new common attributes not yet in the library
 • Updates the file, validates, commits, pushes a branch
 • Opens (or updates) a PR via GitHub API
"""
import json, os, subprocess, datetime, pathlib, requests, openai, sys, re
from typing import Any, Dict
from constants import classify_attr

ROOT       = pathlib.Path(__file__).resolve().parents[1]
ATTR_FILE  = ROOT / "attributes" / "consolidated_attributes.json"
CATALOG_DIR = ROOT / "data" / "product_catalogs"
BRANCH     = f"codex/attr-{datetime.date.today()}"

openai.api_key = os.getenv("OPENAI_API_KEY")

# detect dry-run argument
DRY_RUN = "--dry-run" in sys.argv

def git(*args):
    subprocess.check_call(["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL)

def load_attributes():
    with ATTR_FILE.open() as f:
        return json.load(f)

def ask_codex(prompt: str) -> str:
    """Call OpenAI Chat API compatible with both <1.0 and >=1.0 clients."""
    messages = [
        {"role": "system", "content": "You are an expert taxonomy curator."},
        {"role": "user", "content": prompt},
    ]
    # New client (openai>=1.0) exposes OpenAI class
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI()  # api_key is read from env var
        rsp = client.chat.completions.create(
            model="gpt-4o-preview",
            messages=messages,
            temperature=0.2,
            max_tokens=800,
        )
        return rsp.choices[0].message.content.strip()
    # Fallback to old API (<1.0)
    rsp = openai.ChatCompletion.create(
        model="gpt-4o-preview",
        messages=messages,
        temperature=0.2,
        max_tokens=800,
    )
    return rsp.choices[0].message.content.strip()

def extract_specs(text: str):
    """Parse bullet-list specs from raw catalog text.

    Recognises leading "*" or "-" and splits lines of the form
        * Operating Weight: 67,500 lb (30,600 kg)

    Returns list of dicts with keys:
        name, value, unit, alt_value, alt_unit (alt_* optional).
    """
    specs = []
    bullet_pat = re.compile(r"^[\*\-]\s*(.+?):\s*(.+)$")
    unit_pat  = re.compile(r"(?P<val>[\d,\.]+)\s*(?P<unit>[a-zA-Z/%]+)")
    for line in text.splitlines():
        m = bullet_pat.match(line.strip())
        if not m:
            continue
        name, rhs = m.groups()
        # primary number + unit
        primary = unit_pat.search(rhs)
        alt = None
        if "(" in rhs and ")" in rhs:
            inside = rhs[rhs.find("(")+1:rhs.rfind(")")]
            alt = unit_pat.search(inside)
        spec = {"name": name.strip()}
        if primary:
            spec["value"] = float(primary.group("val").replace(',', '')) if primary.group("val") else None
            spec["unit"] = primary.group("unit")
        if alt:
            spec["alt_value"] = float(alt.group("val").replace(',', ''))
            spec["alt_unit"] = alt.group("unit")
        # determine category using heuristics
        spec["category"] = classify_attr(name, rhs)
        specs.append(spec)
    return specs

def build_prompt(current_attrs, specs):
    schema_reminder = (
        "ATTRIBUTE LIBRARY RULES:\n"
        "- Attributes are defined once in consolidated_attributes.json using snake_case keys.\n"
        "- Each attribute object must have name, type, category, optional unit.\n"
        "- category must be 'physics' or 'brand'. Units only allowed for physics attributes.\n"
    )
    excavator_example = (
        "EXCAVATOR SPEC EXAMPLE:\n"
        "* Operating Weight: 67,500 lb (30,600 kg)\n"
        "* Engine Model: Cat C7.1 ACERT\n"
        "* Net Power: 204 hp (152 kW)\n"
        "* Maximum Dig Depth: 24 ft 1 in (7.34 m)\n"
        "* Maximum Reach at Ground Level: 35 ft 10 in (10.92 m)\n"
    )
    rules_block = (
        "## ATTRIBUTE CATEGORISATION RULES\n"
        "• \"physics\" attributes measure properties of matter, energy, geometry, or performance.\n"
        "  - always numeric and/or carry SI or Imperial units (kg, lb, ft, psi, kW, V …).\n"
        "  - examples: Operating Weight, Engine Power, Lift Capacity, Voltage, Track Width.\n"
        "• \"brand\" attributes identify a specific manufacturer, part, or marketing label.\n"
        "  - usually strings or codes: Manufacturer, Model Number, Series, Part ID.\n"
        "• NEVER mark an attribute with units as \"brand\".\n"
        "• NEVER mark a manufacturer / model as \"physics\".\n"
        "Return `category` exactly \"physics\" or \"brand\".\n"
    )
    prompt = (
        f"{rules_block}\n\n" +
        f"{schema_reminder}\n\n"
        f"{excavator_example}\n\n"
        "KNOWN ATTRIBUTES (JSON):\n" + json.dumps(current_attrs, indent=2) + "\n\n" +
        "CATALOG SPECS PARSED (JSON, may include alt_value/alt_unit):\n" + json.dumps(specs, indent=2) + "\n\n" +
        "Suggest up to FIVE NEW attributes not yet present, return EXACT JSON object: {\"new_attributes\": {...}}"
    )
    return prompt

def propose(dry: bool = False):
    data = load_attributes()
    existing = set(data["attributes"].keys())

    # load one sample catalog text (first file)
    sample_text = ""
    sample_path = next(CATALOG_DIR.rglob("*.txt"), None)
    if sample_path and sample_path.exists():
        sample_text = sample_path.read_text(errors="ignore")
    specs = extract_specs(sample_text)

    prompt = build_prompt(data["attributes"], specs)
    try:
        raw = ask_codex(prompt)
        parsed = json.loads(raw)
        new_attrs = {k:v for k,v in parsed["new_attributes"].items() if k not in existing}
    except Exception as e:
        print("Codex reply unparsable:", e)
        return None
    if not new_attrs:
        return None
    if not dry:
        data["attributes"].update(new_attrs)

        # write back: consolidated file or per-file
        if ATTR_FILE.exists():
            with ATTR_FILE.open("w") as f:
                json.dump(data, f, indent=2)
        else:
            attr_dir = ROOT / "attributes"
            attr_dir.mkdir(exist_ok=True)
            for code, obj in new_attrs.items():
                with (attr_dir / f"{code}.json").open("w") as f:
                    json.dump(obj, f, indent=2)
    return new_attrs.keys()

def main():
    if DRY_RUN:
        print("[Dry-Run] Parsing catalogs and querying Codex…\n")
        added = propose(dry=True)
        print("\n[Done] No files written. Suggested attribute codes:", list(added) if added else "none")
        return
    git("fetch", "origin")
    try:
        git("checkout", BRANCH)
    except subprocess.CalledProcessError:
        git("checkout", "-b", BRANCH)

    added = propose()
    if not added:
        print("No new attributes proposed.")
        sys.exit(0)

    # local validation
    subprocess.check_call(["python", "scripts/validate.py"], cwd=ROOT)

    git("add", "attributes/consolidated_attributes.json")
    git("commit", "-m", f"chore(codex): add attributes {', '.join(added)}")
    git("push", "-f", "origin", BRANCH)

    # open / update PR
    repo = os.getenv("GITHUB_REPOSITORY", "underthemoss/construction-taxonomy")
    gh_token = os.getenv("GITHUB_TOKEN")
    if not gh_token:
        # Dynamically fetch installation token using helper
        import subprocess, pathlib, os
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
    # check existing PR
    prs = requests.get(f"{api}/pulls?head={repo.split('/')[0]}:{BRANCH}",
                       headers=headers, timeout=20).json()
    if prs:
        print("PR already exists; branch just force-pushed.")
        return
    body = ("### Codex attribute proposal\n"
            "Automated PR adding new attribute definitions suggested by Codex.\n\n"
            "- [ ] Human review required (>=1 CODEOWNER)\n"
            "- Source: LLM (Codex)\n")
    requests.post(f"{api}/pulls",
                  headers=headers,
                  json={
                      "title": "feat: Codex attribute update",
                      "head": BRANCH,
                      "base": "main",
                      "body": body,
                      "maintainer_can_modify": True
                  },
                  timeout=20)
if __name__ == "__main__":
    main()
