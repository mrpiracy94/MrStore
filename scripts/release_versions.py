"""Keep ZimaOS package revisions truthful across safe releases and quarantines.

The upstream software version is NOT the MrStore package revision.
Automatic revision changes require a changed image reference approved by the
release security gate. A version ledger survives temporary quarantine.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import yaml

VERSION = re.compile(r"^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$")


def parse_version(value: object, app_id: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError(f"{app_id}: non-semver package version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def format_version(parts: tuple[int, int, int]) -> str:
    return ".".join(map(str, parts))


def service_images(compose: dict, app_id: str) -> dict[str, str]:
    services = compose.get("services") if isinstance(compose, dict) else None
    if not isinstance(services, dict) or not services:
        raise ValueError(f"{app_id}: missing services")
    images = {}
    for name, spec in services.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("image"), str):
            raise ValueError(f"{app_id}: invalid image in service {name}")
        images[name] = spec["image"]
    return images


def read_previous(previous: Path) -> tuple[dict[str, dict], int]:
    """Load published app versions, including historical quarantined apps."""
    index_path = previous / "index.json"
    if not index_path.is_file():
        raise ValueError("Previous published index.json not found; refusing to reset package versions")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = index.get("apps")
    if not isinstance(entries, list):
        raise ValueError("Previous index.json has invalid apps list")
    active = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Previous index.json has an invalid app entry")
        app_id = item["id"]
        if app_id in active:
            raise ValueError(f"Duplicate previous app ID: {app_id}")
        parse_version(item.get("version"), app_id)
        active[app_id] = item

    ledger_path = previous / "release-versions-state.json"
    snapshots = {}
    if ledger_path.is_file():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if not isinstance(ledger, dict) or ledger.get("schema") != 1 or not isinstance(ledger.get("apps"), dict):
            raise ValueError("Invalid previous version ledger")
        for app_id, item in ledger["apps"].items():
            if not isinstance(app_id, str) or not isinstance(item, dict):
                raise ValueError("Invalid ledger app entry")
            parse_version(item.get("version"), app_id)
            images = item.get("images")
            if not isinstance(images, dict) or not images or any(
                    not isinstance(k, str) or not isinstance(v, str) for k, v in images.items()):
                raise ValueError(f"{app_id}: invalid image references in version ledger")
            snapshots[app_id] = item
    for app_id, item in active.items():
        prev_compose = previous / "apps" / app_id / "docker-compose.yml"
        if not prev_compose.is_file():
            raise ValueError(f"{app_id}: previous published compose is missing")
        images = service_images(yaml.safe_load(prev_compose.read_text(encoding="utf-8")), app_id)
        if ledger_path.is_file():
            stored = snapshots.get(app_id)
            if not stored or stored["version"] != item["version"] or stored["images"] != images:
                raise ValueError(f"{app_id}: previous ledger differs from published catalog")
        else:
            meta_path = previous / "apps" / app_id / "meta.json"
            prior_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
            if not isinstance(prior_meta, dict):
                raise ValueError(f"{app_id}: previous metadata is not an object")
            snapshots[app_id] = {
                "version": item["version"], "images": images,
                "update_at": prior_meta.get("update_at"),
                "release_note": prior_meta.get("release_note"),
            }
    return snapshots, len(active)


def promote(stage: Path, previous: Path, today: date | None = None) -> dict:
    """Update staged approved apps only. Never touch source, containers or quarantined apps."""
    today = today or date.today()
    snapshots, previous_count = read_previous(previous)
    paths = sorted((stage / "Apps").glob("*/docker-compose.yml"))
    if not paths:
        raise ValueError("Staged release is empty")
    results = []
    staged_ids = set()
    for manifest_path in paths:
        compose = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        meta = compose.get("x-casaos") if isinstance(compose, dict) else None
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
            raise ValueError(f"{manifest_path}: missing x-casaos.id")
        app_id = meta["id"]
        if app_id in staged_ids:
            raise ValueError(f"{app_id}: duplicate staged application ID")
        staged_ids.add(app_id)
        original_meta = dict(meta)
        source_version = parse_version(meta.get("version"), app_id)
        images = service_images(compose, app_id)
        before = snapshots.get(app_id)
        if before is None:
            reason = "new-to-store"
            old_version_text = None
            changed_services = []
        else:
            old_version = parse_version(before["version"], app_id)
            old_version_text = format_version(old_version)
            old_images = before["images"]
            changed_services = sorted(k for k in set(old_images) | set(images)
                                      if old_images.get(k) != images.get(k))
            newer_version = max(source_version, old_version)
            if changed_services and newer_version <= old_version:
                newer_version = (old_version[0], old_version[1], old_version[2] + 1)
            meta["version"] = format_version(newer_version)
            if changed_services:
                meta["update_at"] = today.isoformat()
                meta["release_notes"] = {
                    "en_US": "MrStore package update: reviewed Docker image references changed "
                             "and passed the release security gate. Consult upstream release notes "
                             "and back up persistent data before updating."
                }
                reason = "approved-image-change"
            elif newer_version > old_version:
                reason = "explicit-source-version"
            else:
                reason = "retained"
                if isinstance(before.get("update_at"), str):
                    meta["update_at"] = before["update_at"]
                if isinstance(before.get("release_note"), str) and before["release_note"]:
                    meta["release_notes"] = {"en_US": before["release_note"]}
        if meta != original_meta:
            manifest_path.write_text(
                yaml.safe_dump(compose, sort_keys=False, allow_unicode=True),
                encoding="utf-8")
        snapshot = {
            "version": meta["version"],
            "images": images,
            "update_at": meta.get("update_at"),
            "release_note": (meta.get("release_notes") or {}).get("en_US"),
        }
        snapshots[app_id] = snapshot
        results.append({
            "id": app_id, "old": old_version_text,
            "new": meta["version"], "reason": reason,
            "changed_services": changed_services,
        })

    return {
        "published_previous_apps": previous_count,
        "approved_apps": len(results),
        "image_updates": sum(r["reason"] == "approved-image-change" for r in results),
        "explicit_updates": sum(r["reason"] == "explicit-source-version" for r in results),
        "carried_forward": sum(r["reason"] == "retained" for r in results),
        "new_to_store": sum(r["reason"] == "new-to-store" for r in results),
        "apps": results,
        "state": {"schema": 1, "apps": dict(sorted(snapshots.items()))},
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("out/release-versions.json"))
    p.add_argument("--state-output", type=Path, default=Path("out/release-versions-state.json"))
    args = p.parse_args()
    report = promote(args.stage, args.previous)
    state = report.pop("state")
    for path, data in ((args.output, report), (args.state_output, state)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    print("MrStore package versions:",
          report["image_updates"], "approved image changes;",
          report["carried_forward"], "versions retained;",
          report["new_to_store"], "new apps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
