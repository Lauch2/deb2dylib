#!/usr/bin/env python3
"""Zentrale Konfiguration für deb2dylib-Skripte.

Liest Werte in dieser Reihenfolge: echte Umgebungsvariablen > ``config.env``
(nicht im Repo) > ``.env`` > Standardwerte.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


for _candidate in ("config.env", ".env"):
    _load_env_file(ROOT / _candidate)


def get(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or default


def path(name: str, default: str) -> Path:
    raw = get(name, default) or default
    candidate = Path(raw).expanduser()
    return candidate if candidate.is_absolute() else (ROOT / candidate)


# --- Ausgabe ---
OUT_DIR = path("OUT_DIR", "tweaksOrder")

# --- GitHub (tweak_finder.py) ---
GITHUB_TOKEN = get("GITHUB_TOKEN", "")


if __name__ == "__main__":
    print(f"ROOT     = {ROOT}")
    print(f"OUT_DIR  = {OUT_DIR}")
    print(f"GITHUB_TOKEN = {'(gesetzt)' if GITHUB_TOKEN else '(nicht gesetzt)'}")