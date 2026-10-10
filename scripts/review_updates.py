#!/usr/bin/env python3
"""Risk-classify app updates on pull requests; never install third-party manifests."""
import argparse
import json
import posixpath
from pathlib import Path
import re
import subprocess
import sys
import yaml

from catalog import ROOT

DATA_SERVICES = re.compile(r"postgres|mariadb|mysql|redis|valkey|meili|mongo|clickhouse|sqlite|database|db$", re.I)
SENSITIVE = ("volumes", "ports", "privileged", "network_mode", "security_opt",
             "cap_add", "devices", "pid", "user", "environment", "command", "entrypoint")


def baseline(base: str, path: str) -> dict | None:
    result = subprocess.run(["git", "show", f"{base}:{path}"],
                            cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        return None
    return yaml.safe_load(result.stdout)


def classify(old: dict | None, new: dict, folder: str) -> dict:
    if old is None:
        return {"app": folder, "risk": "new", "reasons": ["new application; review required"]}
    old_services = old.get("services") or {}
    new_services = new.get("services") or {}
    reasons = []
    severe = False
    for name in set(old_services) | set(new_services):
        previous = old_services.get(name)
        current = new_services.get(name)
        if not isinstance(previous, dict) or not isinstance(current, dict):
            severe = True
            reasons.append(f"service {name}: added or removed")
            continue
        if previous.get("image") != current.get("image"):
            reasons.append(f"{name}: Docker image reference changed")
            if DATA_SERVICES.search(name + " " + str(previous.get("image", ""))):
                severe = True
                reasons.append(f"{name}: database/stateful dependency changed")
        for field in SENSITIVE:
            if previous.get(field) != current.get(field):
                severe = True
                reasons.append(f"{name}: {field} changed")
    old_meta = old.get("x-casaos") or {}
    new_meta = new.get("x-casaos") or {}
    for field in ("id", "main", "architectures"):
        if old_meta.get(field) != new_meta.get(field):
            severe = True
            reasons.append(f"x-casaos.{field} changed")
    return {"app": folder, "risk": "high" if severe else ("review" if reasons else "metadata"),
            "reasons": sorted(set(reasons))}


IMMICH_POSTGRES = re.compile(r"(?:^|/)immich-app/postgres:(\d+)-")


def _pg_major(image: object) -> int | None:
    match = IMMICH_POSTGRES.search(str(image or ""))
    return int(match.group(1)) if match else None


def _postgres_data_source(service: dict) -> str | None:
    for volume in service.get("volumes") or []:
        if isinstance(volume, dict):
            if volume.get("target") == "/var/lib/postgresql/data":
                return str(volume.get("source") or "")
        elif isinstance(volume, str):
            fields = volume.split(":")
            if len(fields) >= 2 and fields[1] == "/var/lib/postgresql/data":
                return fields[0]
    return None


def immich_major_upgrade_hazards(old: dict | None, new: dict, folder: str) -> list[str]:
    """Reject in-place PG major changes on the actual persistent data directory.

    This never performs database commands. A major version migration must use
    a NEW directory populated by a separately proven restore or upgrade.
    """
    if folder != "immich" or old is None:
        return []
    prev = (old.get("services") or {}).get("immich-database")
    curr = (new.get("services") or {}).get("immich-database")
    if not isinstance(prev, dict):
        return []
    former = _pg_major(prev.get("image"))
    # Renaming or deleting the existing DB service is not a safe major upgrade.
    # Require an independently proven migration before accepting the update.
    if former is not None and not isinstance(curr, dict):
        return ["Immich PostgreSQL: existing immich-database service removed or "
                "renamed; preserve the old database and require a tested migration "
                "and rollback before any catalog deployment"]
    if not isinstance(curr, dict):
        return []
    future = _pg_major(curr.get("image"))
    if former is None:
        return []
    if former == future and future is not None:
        return []
    # Replacing the official Immich PostgreSQL image with an unrecognised
    # image is equally unsafe on the old directory: its data format is unknown.
    if future is None and prev.get("image") == curr.get("image"):
        return []
    old_volume = _postgres_data_source(prev)
    new_volume = _postgres_data_source(curr)
    # Normalize equivalent absolute Linux paths: a rewritten alias such as
    # /DATA/AppData/immich/postgres/. must never bypass the PG major gate.
    # Symlink resolution cannot be proven offline and needs device review.
    if old_volume:
        old_volume = ("/" + posixpath.normpath(old_volume).lstrip("/")
                      if old_volume.startswith("/") else None)
    if new_volume:
        new_volume = ("/" + posixpath.normpath(new_volume).lstrip("/")
                      if new_volume.startswith("/") else None)
    overlap = bool(old_volume and new_volume and (
        new_volume == old_volume or
        new_volume.startswith(old_volume.rstrip("/") + "/") or
        old_volume.startswith(new_volume.rstrip("/") + "/")
    ))
    if not old_volume or not new_volume or overlap:
        return [
            f"Immich PostgreSQL {former}->{future or 'unknown'}: direct major/unknown image change "
            "with the previous/missing data directory is forbidden. "
            "Keep the PG14 directory untouched and migrate/restore into "
            "a separate persistent directory with a tested backup, restore "
            "and rollback procedure before any catalog image change."
        ]
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "out/update-risk.json")
    args = parser.parse_args()
    diff = subprocess.run(["git", "diff", "--name-only", args.base_sha, "HEAD", "--", "Apps"],
                          cwd=ROOT, text=True, capture_output=True, check=True)
    changed = sorted({
        str(Path(p).parts[1])
        for p in diff.stdout.splitlines()
        if len(Path(p).parts) >= 3 and Path(p).parts[0] == "Apps"
    })
    findings = []
    blocked = []
    for folder in changed:
        path = f"Apps/{folder}/docker-compose.yml"
        current_path = ROOT / path
        if not current_path.exists():
            blocked.append(f"{folder}: app removed without migration plan")
            continue
        candidate = yaml.safe_load(current_path.read_text(encoding="utf-8"))
        previous = baseline(args.base_sha, path)
        finding = classify(previous, candidate, folder)
        blocked.extend(immich_major_upgrade_hazards(previous, candidate, folder))
        if finding["risk"] == "high":
            upgrade_doc = ROOT / "docs" / "upgrades" / (folder + ".md")
            if not upgrade_doc.exists():
                blocked.append(f"{folder}: requires docs/upgrades/{folder}.md "
                               "with backup, migration, testing and rollback plan")
            else:
                body = upgrade_doc.read_text(encoding="utf-8").lower()
                if not all(t in body for t in ("backup", "migra", "test", "rollback")):
                    blocked.append(f"{folder}: upgrade plan must cover backup, migration, tests and rollback")
        findings.append(finding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"changes": findings, "blocked": blocked}, indent=2, ensure_ascii=False) + "\n")
    print(f"Reviewed {len(findings)} changed applications")
    for entry in findings:
        print(f" - {entry['app']}: {entry['risk']}: {', '.join(entry['reasons'])}")
    for message in blocked:
        print("ERROR: " + message, file=sys.stderr)
    if blocked:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
