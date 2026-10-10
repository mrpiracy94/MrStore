#!/usr/bin/env python3
"""Deterministic 6 -> 233 editorial rollout in +12 increments (+11 final).

Repackages each already-built official ZimaOS v2 distribution by REMOVING
unselected entries. It never invents installs, images, CVE findings or approval.
This is intentionally separate from the authenticated safe-release pipeline.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile

from featured import load_featured

PREFIX = "io.github.mrpiracy94."
INITIAL = ("homeassistant", "immich", "jellyfin", "nextcloud", "qbittorrent", "vaultwarden")
TARGET = 233
BATCH = 12


def read_plan(path: Path, known: set[str] | None = None) -> tuple[str, ...]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if set(policy) != {"schema", "target_count", "batch_size", "starting_count",
                       "description", "apps"}:
        raise ValueError("Invalid rollout plan schema")
    if (policy["schema"] != 1 or policy["target_count"] != TARGET or
            policy["batch_size"] != BATCH or policy["starting_count"] != len(INITIAL)):
        raise ValueError("Unexpected rollout counts")
    if not isinstance(policy["description"], str) or not policy["description"]:
        raise ValueError("Plan description is required")
    apps = policy["apps"]
    if (not isinstance(apps, list) or len(apps) != TARGET or len(set(apps)) != TARGET
            or any(not isinstance(x, str) or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", x)
                   for x in apps)):
        raise ValueError("Rollout must list exactly 233 unique valid app slugs")
    if set(apps[:len(INITIAL)]) != set(INITIAL):
        raise ValueError("Rollout must preserve the six currently public apps")
    if "steamos" in apps:
        raise ValueError("Retired SteamOS may not be reintroduced")
    if known is not None and not set(apps) <= known:
        raise ValueError("Missing source app definitions: " + str(sorted(set(apps) - known)))
    return tuple(apps)


def milestones(total: int = TARGET) -> list[int]:
    if total != TARGET:
        raise ValueError("Unexpected rollout target")
    out = []
    n = len(INITIAL)
    while n < TARGET:
        n = min(n + BATCH, TARGET)
        out.append(n)
    return out


def index(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
        raise ValueError("Missing app index")
    ids = [r.get("id") if isinstance(r, dict) else None for r in data["apps"]]
    if not all(isinstance(x, str) and x.startswith(PREFIX) for x in ids):
        raise ValueError("Invalid app ID")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate app ID")
    if "app_count" in data and data["app_count"] != len(ids):
        raise ValueError("Incorrect index count")
    return data


def _trim(data: dict, allowed: set[str]) -> dict:
    cloned = dict(data)
    cloned["apps"] = [row for row in data["apps"] if row["id"] in allowed]
    if "app_count" in data:
        cloned["app_count"] = len(cloned["apps"])
    if {row["id"] for row in cloned["apps"]} != allowed:
        raise ValueError("Trimmed index does not match requested milestone")
    return cloned


def _json(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _check_metadata(source: Path) -> None:
    data = (source / "metadata.tar.gz").read_bytes()
    parts = (source / "metadata.sha256").read_text(encoding="ascii").split()
    if (len(parts) != 2 or parts[1] != "metadata.tar.gz"
            or not re.fullmatch(r"[a-f0-9]{64}", parts[0])
            or hashlib.sha256(data).hexdigest() != parts[0]):
        raise ValueError("Metadata checksum mismatch")


def _repack(target: Path, allowed: set[str], withdrawn: set[str]) -> None:
    archive = target / "metadata.tar.gz"
    temp = target / "metadata.tar.gz.new"
    kept = []
    seen = set()
    try:
        with tarfile.open(archive, "r:gz") as original:
            for entry in original:
                name = entry.name.removeprefix("./").rstrip("/")
                parts = Path(name).parts
                if not name or name.startswith("/") or ".." in parts or name in seen:
                    raise ValueError("Unsafe or duplicated metadata path " + name)
                seen.add(name)
                if any(x in withdrawn for x in parts):
                    continue
                if not (entry.isfile() or entry.isdir()):
                    raise ValueError("Unsupported TAR entry: " + name)
                content = original.extractfile(entry).read() if entry.isfile() else None
                if content is not None and name in ("index.json", "index.pt_PT.json"):
                    data = json.loads(content)
                    if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
                        raise ValueError("Malformed metadata index")
                    content = _json(_trim(data, allowed))
                    entry.size = len(content)
                elif content is not None and any(x.encode("utf-8") in content for x in withdrawn):
                    raise ValueError("Unrecognized reference in metadata " + name)
                kept.append((entry, content))
        with temp.open("wb") as handle:
            with gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as dest:
                    for entry, content in kept:
                        dest.addfile(entry, io.BytesIO(content) if content is not None else None)
        with tarfile.open(temp, "r:gz") as check:
            for entry in check:
                if any(x in withdrawn for x in Path(entry.name).parts):
                    raise ValueError("Removed application still present inside archive")
                if entry.isfile() and entry.name.removeprefix("./") in ("index.json", "index.pt_PT.json"):
                    data = json.load(check.extractfile(entry))
                    if {a["id"] for a in data["apps"]} != allowed:
                        raise ValueError("Archived index does not match milestone")
        temp.replace(archive)
        (target / "metadata.sha256").write_text(
            hashlib.sha256(archive.read_bytes()).hexdigest() + "  metadata.tar.gz\n",
            encoding="ascii")
    finally:
        temp.unlink(missing_ok=True)


def curate(full: Path, output: Path, plan: tuple[str, ...], count: int) -> dict:
    if count not in milestones():
        raise ValueError("Count must be an explicit 12-app milestone (last adds 11)")
    if output.exists():
        raise ValueError("Refusing to overwrite existing output")
    primary = index(full / "index.json")
    translated = index(full / "index.pt_PT.json")
    expected = {PREFIX + slug for slug in plan}
    if ({r["id"] for r in primary["apps"]} != expected or
            {r["id"] for r in translated["apps"]} != expected):
        raise ValueError("Full catalog does not match the exact 233 source definitions")
    status_file = full / "release-status.json"
    if status_file.is_file():
        status = json.loads(status_file.read_text(encoding="utf-8"))
        if status.get("certification") != "not_assessed":
            raise ValueError("Cannot rewrite a security-certified release")
    _check_metadata(full)
    allowed = {PREFIX + slug for slug in plan[:count]}
    withdrawn = expected - allowed
    source_dirs = full / "apps"
    if ({item.name for item in source_dirs.iterdir() if item.is_dir()} != expected
            or any(item.is_symlink() or not item.is_dir() for item in source_dirs.iterdir())):
        raise ValueError("Full catalog app directories disagree with index")
    shutil.copytree(full, output, symlinks=False)
    try:
        for name in withdrawn:
            shutil.rmtree(output / "apps" / name)
        (output / "index.json").write_bytes(_json(_trim(primary, allowed)))
        (output / "index.pt_PT.json").write_bytes(_json(_trim(translated, allowed)))
        _repack(output, allowed, withdrawn)
        if status_file.is_file():
            status = json.loads((output / "release-status.json").read_text(encoding="utf-8"))
            status["approved"] = sorted(x.removeprefix(PREFIX) for x in allowed)
            status["approved_count"] = count
            status["featured_count"] = count
            status["deferred"] = sorted(x.removeprefix(PREFIX) for x in withdrawn)
            status["deferred_count"] = 253 - count
            status["certification"] = "not_assessed"
            status["policy"] = "Editorial listing only; security verification pending"
            (output / "release-status.json").write_bytes(_json(status))
        if ({r["id"] for r in index(output / "index.json")["apps"]} != allowed or
                {r["id"] for r in index(output / "index.pt_PT.json")["apps"]} != allowed or
                {item.name for item in (output / "apps").iterdir()} != allowed):
            raise ValueError("Subset verification failed")
        _check_metadata(output)
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {"stage": count, "added_since_previous": count - (count - BATCH if count != TARGET else 222),
            "apps": list(plan[:count]), "certification": "not_assessed"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--policy-output", type=Path)
    p.add_argument("--full-dist", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--count", type=int)
    args = p.parse_args()
    known = {x.parent.name for x in (args.root / "Apps").glob("*/docker-compose.yml")}
    plan = read_plan(args.plan, known)
    if args.policy_output:
        args.policy_output.parent.mkdir(parents=True, exist_ok=True)
        args.policy_output.write_bytes(_json({
            "schema": 1, "description": "Uncertified editorial 233-app rollout",
            "apps": list(plan)}))
    if args.full_dist and args.output and args.count:
        print(json.dumps(curate(args.full_dist, args.output, plan, args.count)))
    else:
        print(json.dumps({"source": len(known), "target": len(plan),
                          "milestones": milestones(), "withheld": len(known) - len(plan)}))


if __name__ == "__main__":
    main()
