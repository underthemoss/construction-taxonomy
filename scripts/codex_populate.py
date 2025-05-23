#!/usr/bin/env python
"""
Codex attribute proposer:
 • Reads attributes/attributes.json
 • Asks Codex for 1-5 new common attributes not yet in the library
 • Updates the file, validates, commits, pushes a branch
 • Opens (or updates) a PR via GitHub API
"""
import json, os, subprocess, datetime, pathlib, requests, openai, sys
ROOT       = pathlib.Path(__file__).resolve().parents[1]
ATTR_FILE  = ROOT / "attributes" / "attributes.json"
BRANCH     = f"codex/attr-{datetime.date.today()}"

openai.api_key = os.getenv("OPENAI_API_KEY")

def git(*args):
    subprocess.check_call(["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL)

def load_attributes():
    with ATTR_FILE.open() as f:
        return json.load(f)

def ask_codex(prompt):
    rsp = openai.ChatCompletion.create(
        model="gpt-4o-preview",
        messages=[
            {"role":"system","content":"You are an expert taxonomy curator."},
            {"role":"user",  "content": prompt}
        ],
        temperature=0.2,
        max_tokens=800
    )
    return rsp.choices[0].message.content.strip()

def propose():
    data = load_attributes()
    existing = set(data["attributes"].keys())
    prompt = (
      "Below is a JSON of known product attributes for the construction industry. "
      "Suggest up to FIVE NEW physics- or brand-based attributes commonly present "
      "in ≥80 % of equipment records that are NOT already listed. "
      "Return EXACTLY a JSON object: {\"new_attributes\": {\"code\": { ... }, ... }}.\n\n"
      + json.dumps(data["attributes"])
    )
    try:
        raw = ask_codex(prompt)
        parsed = json.loads(raw)
        new_attrs = {k:v for k,v in parsed["new_attributes"].items() if k not in existing}
    except Exception as e:
        print("Codex reply unparsable:", e)
        return None
    if not new_attrs:
        return None
    data["attributes"].update(new_attrs)
    with ATTR_FILE.open("w") as f:
        json.dump(data, f, indent=2)
    return new_attrs.keys()

def main():
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

    git("add", "attributes/attributes.json")
    git("commit", "-m", f"chore(codex): add attributes {', '.join(added)}")
    git("push", "-f", "origin", BRANCH)

    # open / update PR
    repo = os.getenv("GITHUB_REPOSITORY", "underthemoss/construction-taxonomy")
    gh_token = os.getenv("GITHUB_TOKEN")
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
