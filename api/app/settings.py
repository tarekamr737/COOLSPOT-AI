"""Small server-side environment loader without exposing secrets to the web app."""

import os
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_project_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ if environ is None else environ)
    return values
