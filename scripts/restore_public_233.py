#!/usr/bin/env python3
"""Restore exactly 233 editorial ZimaOS apps from verified *legacy* 253 snapshot.

Removal-only from an existing v2 builder output; does not claim CVE approval.
The historical snapshot contains published assets and manifests, not security
attestations. Never mix snapshots, invent new apps, or modify a certified release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from featured import load_featured
from rollout_233 import PREFIX, TARGET, read_plan, index, _trim, _json, _check_metadata, _repack

SNAPSHOT_SIZE = 253


def restore(snapshot: Path, output: Path, root: Path) -> dict:
    known = {p.parent.name for p in (root / "Apps").glob("*/docker-compose.yml")}
    if len(known) != SNAPSHOT_SIZE or "steamos" in known:
        raise ValueError("Unexpected source inventory; SteamOS must be retired")
    plan = read_plan(root / "data/rollout-233.json", known)
    featured = load_featured(root / "data/featured-apps.json", known)
    if list(plan) != list(featured):
        raise ValueError("Current editorial list differs from the approved 233-app rollout")
    original = index(snapshot / "index.json")
    pt = index(snapshot / "index.pt_PT.json")
    original_ids = {entry["id"] for entry in original["apps"]}
    requested = {PREFIX + slug for slug in plan}
    if (len(original_ids) != SNAPSHOT_SIZE or original_ids != {entry["id"] for entry in pt["apps"]}
            or not requested <= original_ids or len(requested) != TARGET
            or PREFIX + "steamos" in original_ids):
        raise ValueError("Historical 253-app metadata is incomplete/inconsistent")
    if (snapshot / "release-status.json").exists():
        raise ValueError("Historical source is an audited release; manual editorial rewrite forbidden")
    dirs = snapshot / "apps"
    if (dirs.is_symlink() or {p.name for p in dirs.iterdir()} != original_ids or
            any(not p.is_dir() or p.is_symlink() for p in dirs.iterdir())):
        raise ValueError("Historical app assets do not exactly match the 253-entry index")
    _check_metadata(snapshot)
    if output.exists():
        raise ValueError("Refusing to overwrite output directory")
    removed = original_ids - requested
    if len(removed) != SNAPSHOT_SIZE - TARGET:
        raise ValueError("Incorrect number of apps deferred")
    shutil.copytree(snapshot, output, symlinks=False)
    try:
        for app_id in removed:
            path = output / "apps" / app_id
            if path.is_symlink() or not path.is_dir():
                raise ValueError("Unsafe application assets: " + app_id)
            shutil.rmtree(path)
        (output / "index.json").write_bytes(_json(_trim(original, requested)))
        (output / "index.pt_PT.json").write_bytes(_json(_trim(pt, requested)))
        _repack(output, requested, removed)
        if ({entry["id"] for entry in index(output / "index.json")["apps"]} != requested
                or {entry["id"] for entry in index(output / "index.pt_PT.json")["apps"]} != requested
                or {p.name for p in (output / "apps").iterdir()} != requested):
            raise ValueError("Result does not contain exactly the 233 selected apps")
        _check_metadata(output)
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {"published_apps": TARGET, "preserved_source_apps": len(known),
            "deferred": sorted(x.removeprefix(PREFIX) for x in removed),
            "security_certification": "not_assessed",
            "legacy_snapshot": "4702d19a0340b39cece67b024c16f1ec963de367"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    opts = p.parse_args()
    print(json.dumps(restore(opts.snapshot, opts.output, opts.root),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
