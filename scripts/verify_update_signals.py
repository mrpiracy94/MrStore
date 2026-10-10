"""Fail closed when a published ZimaOS package claims an update without a new hash.

This checks only approved app revisions (image changes or explicit package bumps).
Changing Docker tags or metadata must not silently ship an unusable update
signal to ZimaOS App Store v2. It does not verify native NAS notification badges.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_versions import parse_version


def read_index(root: Path) -> dict[str, dict]:
    path = root / "index.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("apps") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{path}: invalid index apps list")
    result: dict[str, dict] = {}
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError(f"{path}: invalid app")
        app_id = item["id"]
        if app_id in result:
            raise ValueError(f"{path}: duplicate app {app_id}")
        if not isinstance(item.get("version"), str) or not isinstance(item.get("content_hash"), str):
            raise ValueError(f"{app_id}: missing package version/hash")
        parse_version(item["version"], app_id)
        if not item["content_hash"]:
            raise ValueError(f"{app_id}: empty content_hash")
        result[app_id] = item
    return result


def verify(previous: Path, published: Path, version_report: Path) -> dict:
    old = read_index(previous)
    new = read_index(published)
    report = json.loads(version_report.read_text(encoding="utf-8"))
    items = report.get("apps")
    if not isinstance(items, list):
        raise ValueError("Invalid release version report")
    seen = set()
    verified = 0
    missing_history = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid package change record")
        app_id = item.get("id")
        if not isinstance(app_id, str) or app_id in seen:
            raise ValueError("Duplicate/invalid change record")
        seen.add(app_id)
        destination = new.get(app_id)
        if destination is None:
            raise ValueError(f"{app_id}: approved app omitted from new index")
        if destination["version"] != item.get("new"):
            raise ValueError(f"{app_id}: staged and published version differ")
        reason = item.get("reason")
        if reason not in ("approved-image-change", "explicit-source-version",
                          "initial-immutable-baseline", "retained", "new-to-store"):
            raise ValueError(f"{app_id}: unknown release reason {reason}")
        before = old.get(app_id)
        if before is None:
            missing_history += 1
            continue
        old_version = parse_version(before["version"], app_id)
        new_version = parse_version(destination["version"], app_id)
        if new_version < old_version:
            raise ValueError(f"{app_id}: version went backwards")
        if reason in ("approved-image-change", "explicit-source-version"):
            if new_version <= old_version:
                raise ValueError(f"{app_id}: change has no higher package version")
            if destination["content_hash"] == before["content_hash"]:
                raise ValueError(f"{app_id}: changed release but content_hash unchanged")
            verified += 1
        elif reason in ("retained", "initial-immutable-baseline"):
            if new_version != old_version:
                raise ValueError(f"{app_id}: unapproved version increase")
    if len(seen) != len(new):
        raise ValueError("Published index contains unaccounted apps")
    return {"checked_apps": len(seen), "verified_update_signals": verified,
            "without_active_previous_entry": missing_history}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--dist", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    details = verify(a.previous, a.dist, a.report)
    print("ZimaOS v2 update signals verified:", details)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
