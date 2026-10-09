"""Keep ZimaOS package revisions monotonic across safe, digest-pinned releases.

The upstream application version is NOT the MrStore package revision. Only the
images actually approved by the release security gate can drive an automatic
revision bump. Previous releases are read from the gh-pages checkout.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import yaml

VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


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


def promote(stage: Path, previous: Path, today: date | None = None) -> dict:
    """Update staged approved apps only. Never touch source, installed containers or quarantined apps."""
    today = today or date.today()
    index_path = previous / "index.json"
    if not index_path.is_file():
        raise ValueError("Previous published index.json not found; refusing to reset package versions")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = index.get("apps")
    if not isinstance(entries, list):
        raise ValueError("Previous index.json has invalid apps list")
    by_id = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Previous index.json has an invalid app entry")
        if entry["id"] in by_id:
            raise ValueError(f"Duplicate previous app ID: {entry['id']}")
        by_id[entry["id"]] = entry

    paths = sorted((stage / "Apps").glob("*/docker-compose.yml"))
    if not paths:
        raise ValueError("Staged release is empty")
    results = []
    for manifest_path in paths:
        compose = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        meta = compose.get("x-casaos") if isinstance(compose, dict) else None
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
            raise ValueError(f"{manifest_path}: missing x-casaos.id")
        app_id = meta["id"]
        original_meta = dict(meta)
        source_version = parse_version(meta.get("version"), app_id)
        images = service_images(compose, app_id)
        before = by_id.get(app_id)
        if before is None:
            results.append({"id": app_id, "old": None,
                            "new": format_version(source_version), "reason": "new-to-store"})
            continue

        old_version = parse_version(before.get("version"), app_id)
        prior_compose = previous / "apps" / app_id / "docker-compose.yml"
        if not prior_compose.is_file():
            raise ValueError(f"{app_id}: previous published compose is missing")
        old_images = service_images(
            yaml.safe_load(prior_compose.read_text(encoding="utf-8")), app_id)
        changed_services = sorted(k for k in set(old_images) | set(images)
                                  if old_images.get(k) != images.get(k))
        newer_version = max(source_version, old_version)
        if changed_services and newer_version <= old_version:
            newer_version = (old_version[0], old_version[1], old_version[2] + 1)
        new_version = format_version(newer_version)
        previous_version = format_version(old_version)

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
            # Preserve the details of the last published package revision.
            old_meta_path = previous / "apps" / app_id / "meta.json"
            if old_meta_path.is_file():
                old_meta = json.loads(old_meta_path.read_text(encoding="utf-8"))
                if isinstance(old_meta, dict):
                    if isinstance(old_meta.get("update_at"), str):
                        meta["update_at"] = old_meta["update_at"]
                    old_note = old_meta.get("release_note")
                    if isinstance(old_note, str) and old_note:
                        meta["release_notes"] = {"en_US": old_note}
        meta["version"] = new_version
        if meta != original_meta:
            manifest_path.write_text(
                yaml.safe_dump(compose, sort_keys=False, allow_unicode=True),
                encoding="utf-8")
        results.append({
            "id": app_id, "old": previous_version,
            "new": new_version, "reason": reason,
            "changed_services": changed_services,
        })

    return {
        "published_previous_apps": len(by_id),
        "approved_apps": len(results),
        "image_updates": sum(r["reason"] == "approved-image-change" for r in results),
        "explicit_updates": sum(r["reason"] == "explicit-source-version" for r in results),
        "carried_forward": sum(r["reason"] == "retained" for r in results),
        "new_to_store": sum(r["reason"] == "new-to-store" for r in results),
        "apps": results,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("out/release-versions.json"))
    args = p.parse_args()
    report = promote(args.stage, args.previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MrStore package versions:",
          report["image_updates"], "approved image changes;",
          report["carried_forward"], "versions retained;",
          report["new_to_store"], "new apps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
