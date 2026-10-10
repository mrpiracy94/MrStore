"""Fail-closed editorial allowlist for the initial MrStore public catalog.

The full source catalog remains untouched and security scans retain their own
policy. Inclusion in this shortlist is NOT equivalent to CVE clearance.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def load_featured(path: Path, known: set[str] | None = None) -> tuple[str, ...]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Featured catalog policy file is missing or is a symlink")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or set(obj) != {"schema", "description", "apps"}:
        raise ValueError("Invalid featured catalog policy format")
    if type(obj["schema"]) is not int or obj["schema"] != 1:
        raise ValueError("Unsupported featured catalog policy schema")
    if not isinstance(obj["description"], str) or not obj["description"].strip():
        raise ValueError("Featured selection must explain its editorial criteria")
    slugs = obj["apps"]
    if (not isinstance(slugs, list) or not slugs or
            any(not isinstance(s, str) or not SLUG.fullmatch(s) for s in slugs) or
            len(slugs) != len(set(slugs))):
        raise ValueError("Featured list contains duplicates or invalid app IDs")
    if known is not None:
        unknown = set(slugs) - known
        if unknown:
            raise ValueError("Featured list refers to missing source apps: "
                             + ", ".join(sorted(unknown)))
    return tuple(slugs)
