#!/usr/bin/env python3
"""Curate an existing *legacy* public index to the six featured apps.

WITHDRAWAL ONLY: never adds/updates an app, approves a vulnerability, or
alters release-status.json. Full audited releases use release_catalog.py.
"""
from __future__ import annotations
import argparse
import copy
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


def inspect_index(path: Path) -> dict:
    idx = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(idx, dict) or not isinstance(idx.get("apps"), list):
        raise ValueError("Invalid public index: " + str(path))
    ids = [app.get("id") if isinstance(app, dict) else None for app in idx["apps"]]
    if any(not isinstance(x, str) or not x.startswith(PREFIX) for x in ids):
        raise ValueError("Unexpected public app ID")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate public app IDs")
    if "app_count" in idx and idx["app_count"] != len(ids):
        raise ValueError("Public app_count mismatch")
    return idx


def narrow(idx: dict, allowed: set[str]) -> dict:
    out = copy.deepcopy(idx)
    out["apps"] = [app for app in out["apps"] if app["id"] in allowed]
    if "app_count" in out:
        out["app_count"] = len(out["apps"])
    return out


def dump(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def validate_digest(site: Path) -> None:
    archive = site / "metadata.tar.gz"
    sha = site / "metadata.sha256"
    if not archive.is_file() or not sha.is_file():
        raise ValueError("Missing original public metadata or checksum")
    parts = sha.read_text(encoding="ascii").strip().split()
    if len(parts) != 2 or parts[1] != "metadata.tar.gz" or not re.fullmatch("[0-9a-f]{64}", parts[0]):
        raise ValueError("Unexpected metadata checksum format")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != parts[0]:
        raise ValueError("Original metadata archive checksum mismatch")


def narrow_archive(site: Path, removed: set[str], allowed: set[str]) -> None:
    target = site / "metadata.tar.gz"
    temp = site / "metadata.tar.gz.pending"
    entries = []
    deleted = 0
    seen = set()
    try:
        with tarfile.open(target, "r:gz") as source:
            for entry in source:
                path = entry.name.removeprefix("./").rstrip("/")
                parts = Path(path).parts
                if not path or path.startswith("/") or ".." in parts or path in seen:
                    raise ValueError("Unsafe/duplicate metadata path: " + path)
                seen.add(path)
                if any(part in removed for part in parts):
                    deleted += 1
                    continue
                if not (entry.isfile() or entry.isdir()):
                    raise ValueError("Unsupported metadata member type: " + path)
                content = source.extractfile(entry).read() if entry.isfile() else None
                if content is not None and path in ("index.json", "index.pt_PT.json"):
                    idx = json.loads(content)
                    if not isinstance(idx, dict) or not isinstance(idx.get("apps"), list):
                        raise ValueError("Malformed archived index")
                    updated = narrow(idx, allowed)
                    if {row["id"] for row in updated["apps"]} != allowed:
                        raise ValueError("Archived index does not cover six selected apps")
                    content = dump(updated)
                    entry.size = len(content)
                elif content is not None and any(name.encode() in content for name in removed):
                    raise ValueError("Unexpected other metadata references removed apps: " + path)
                entries.append((entry, content))
        if deleted < 1:
            raise ValueError("No removed app metadata; legacy archive must be reviewed")
        with temp.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as packed:
                with tarfile.open(fileobj=packed, mode="w") as output:
                    for entry, content in entries:
                        output.addfile(entry, io.BytesIO(content) if content is not None else None)
        with tarfile.open(temp, "r:gz") as verify:
            for entry in verify:
                if any(part in removed for part in Path(entry.name).parts):
                    raise ValueError("Withdrawn application remains in archive")
                if entry.isfile() and entry.name.removeprefix("./") in ("index.json", "index.pt_PT.json"):
                    idx = json.load(verify.extractfile(entry))
                    if {row["id"] for row in idx["apps"]} != allowed:
                        raise ValueError("Archived index disagrees with shortlist")
        temp.replace(target)
        (site / "metadata.sha256").write_text(
            hashlib.sha256(target.read_bytes()).hexdigest() + "  metadata.tar.gz\n",
            encoding="ascii")
    finally:
        temp.unlink(missing_ok=True)


def curate(site: Path, source: Path) -> dict:
    featured = load_featured(source / "data/featured-apps.json",
                             {p.parent.name for p in (source / "Apps").glob("*/docker-compose.yml")})
    if len(featured) != 6:
        raise ValueError("Public pilot must contain exactly six selected apps")
    allowed = {PREFIX + name for name in featured}
    if (site / "release-status.json").exists():
        raise ValueError("Audited release present: cannot manually rewrite security approval evidence")
    index = inspect_index(site / "index.json")
    pt = inspect_index(site / "index.pt_PT.json")
    published = {entry["id"] for entry in index["apps"]}
    if {entry["id"] for entry in pt["apps"]} != published:
        raise ValueError("Public PT and default indexes disagree")
    if not allowed <= published:
        raise ValueError("Required featured app missing from existing public catalog")
    directory = site / "apps"
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Invalid published app directory")
    paths = list(directory.iterdir())
    if any(not p.is_dir() or p.is_symlink() for p in paths):
        raise ValueError("Unexpected file/link in published app directory")
    if {p.name for p in paths} != published:
        raise ValueError("Published app folders differ from public index")
    dropped = published - allowed
    if not dropped:
        return {"changed": False, "public_apps": 6}
    validate_digest(site)
    narrow_archive(site, dropped, allowed)
    (site / "index.json").write_bytes(dump(narrow(index, allowed)))
    (site / "index.pt_PT.json").write_bytes(dump(narrow(pt, allowed)))
    for name in dropped:
        path = directory / name
        if not path.is_dir() or path.is_symlink():
            raise ValueError("Unsafe app folder during curation: " + name)
        shutil.rmtree(path)
    validate_digest(site)
    if {a["id"] for a in inspect_index(site / "index.json")["apps"]} != allowed:
        raise ValueError("Final catalog does not match shortlist")
    if {a["id"] for a in inspect_index(site / "index.pt_PT.json")["apps"]} != allowed:
        raise ValueError("Final Portuguese catalog does not match shortlist")
    if {p.name for p in directory.iterdir()} != allowed:
        raise ValueError("Other public app directories remain")
    return {"changed": True, "public_apps": 6, "removed": len(dropped),
            "featured": list(featured), "certified_release": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(curate(args.site, args.source), indent=2))


if __name__ == "__main__":
    main()
