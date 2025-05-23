#!/usr/bin/env python
"""
Return a short-lived installation token to stdout using only:
  GH_APP_ID
  GH_APP_PRIVATE_KEY  (PEM)
Environment must also provide GITHUB_REPOSITORY (owner/name).
No INSTALLATION_ID secret needed u2013 the script discovers it.
"""
import os, time, jwt, requests, sys

app_id   = os.getenv("GH_APP_ID")
pem      = os.getenv("GH_APP_PRIVATE_KEY")
repo_slug= os.getenv("GITHUB_REPOSITORY")  # e.g. underthemoss/construction-taxonomy
if not (app_id and pem and repo_slug):
    sys.exit("Missing env vars")

# 1ufe0fu20e3 Build JWT
now = int(time.time())
jwt_token = jwt.encode(
    {"iat": now-60, "exp": now+540, "iss": app_id},
    pem, algorithm="RS256"
)

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Accept":        "application/vnd.github+json",
    "User-Agent":    "windsurf-taxonomy-bot"
}

# 2ufe0fu20e3 Find installation that contains our repo
insts = requests.get("https://api.github.com/app/installations",
                     headers=headers, timeout=15).json()
installation_id = next(
    inst["id"] for inst in insts
    if any(r["full_name"] == repo_slug for r in inst.get("repositories", []))
)

# 3ufe0fu20e3 Exchange for installation token
tok = requests.post(
    f"https://api.github.com/app/installations/{installation_id}/access_tokens",
    headers=headers, timeout=15
).json()["token"]

print(tok)
