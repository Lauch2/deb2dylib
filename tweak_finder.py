#!/usr/bin/env python3
"""Hole die neuesten versionierten deb-Assets von bekannten Tweak-Repos.

Nutzen: python3 tweak_finder.py
Optional: GITHUB_TOKEN in config.env für höhere Rate-Limits (60/h ohne Token).
"""
import json
import sys
import urllib.request
from pathlib import Path

from deb2config import GITHUB_TOKEN  # noqa: E402  (lädt config.env)

REPOS = [
    ("YTLite (YouTube)", "dayanch96/YTLite", "arm64"),
    ("H5GG-Revamped (Mod-Engine)", "Mods-Center-iOS/H5GG-Revamped", None),
    ("BHInstagram (Instagram)", "BandarHL/BHInstagram", "arm64"),
    ("Rocket (Instagram)", "annulya/rocket", None),
    ("SafariPlus (Safari)", "opa334/SafariPlus", None),
]

def gh(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tweak-check"})
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

for name, repo, arch in REPOS:
    try:
        d = gh(f"https://api.github.com/repos/{repo}/releases/latest")
        tag = d.get("tag_name", "?")
        assets = d.get("assets", [])
        print(f"\n=== {name} ({repo}) — Tag {tag} ===")
        if not assets:
            print("  (keine Assets im latest-Release)")
        for a in assets:
            n = a["name"]
            if arch and arch not in n and ".dylib" not in n:
                continue
            print(f"  {n}")
            print(f"    {a['browser_download_url']}")
    except Exception as e:
        print(f"\n=== {name} ({repo}) — FEHLER: {e}")