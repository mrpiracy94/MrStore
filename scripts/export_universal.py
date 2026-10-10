"""Export a preview CasaOS/Homeio source archive only from a scanned MrStore release.

The archive is deliberately not labelled a certified CasaOS v1 sysroot package.
No privileged install scripts or unapproved app definitions are embedded.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import yaml

SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DIGEST = re.compile(r"@sha256:[a-f0-9]{64}$")
ASSET_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".json", ".yaml", ".yml", ".md"}
ROOT_FILES = ("store-config.json", "supported-languages.json",
              "category-list.json", "recommend-list.json")
MAX_FILE = 10 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024


def _bytes(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Missing/unsafe regular file: {path}")
    if path.stat().st_size > MAX_FILE:
        raise ValueError(f"Oversized input: {path}")
    return path.read_bytes()


def _check_compose(content: bytes, slug: str) -> None:
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"{slug}: invalid Compose YAML") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{slug}: invalid Compose structure")
    meta = data.get("x-casaos")
    services = data.get("services")
    if not isinstance(meta, dict) or meta.get("id") != f"io.github.mrpiracy94.{slug}":
        raise ValueError(f"{slug}: missing or mismatched x-casaos identity")
    if not isinstance(services, dict) or not services or meta.get("main") not in services:
        raise ValueError(f"{slug}: missing main Docker service")
    for name, service in services.items():
        if not isinstance(service, dict) or not isinstance(service.get("image"), str):
            raise ValueError(f"{slug}/{name}: missing image")
        if not DIGEST.search(service["image"]):
            raise ValueError(f"{slug}/{name}: image not pinned to audited digest")
        env = service.get("environment", {})
        if "CHANGE_ME" in str(env):
            raise ValueError(f"{slug}/{name}: unresolved secret")
        if service.get("privileged") is True or service.get("network_mode") == "host":
            raise ValueError(f"{slug}/{name}: dangerous runtime privilege")
        volumes = service.get("volumes", [])
        if "/var/run/docker.sock" in str(volumes):
            raise ValueError(f"{slug}/{name}: Docker socket mount")


def archive_entries(source: Path, selection: Path) -> dict[str, bytes]:
    """Fail closed if stage and release-selection.json differ."""
    report = json.loads(_bytes(selection).decode("utf-8"))
    approved = report.get("approved")
    count = report.get("approved_count")
    if (not isinstance(approved, list) or not approved
            or type(count) is not int or len(approved) != count
            or any(not isinstance(s, str) or not SLUG.fullmatch(s) for s in approved)
            or len(set(approved)) != count):
        raise ValueError("Invalid/empty approval evidence")
    apps = source / "Apps"
    if not apps.is_dir() or apps.is_symlink():
        raise ValueError("Missing/unsafe staged Apps directory")
    actual = {x.name for x in apps.iterdir() if x.is_dir() and not x.is_symlink()}
    if actual != set(approved):
        raise ValueError("Staged apps differ from security-approved apps")

    entries: dict[str, bytes] = {}
    for name in ROOT_FILES:
        entries[name] = _bytes(source / name)
    for slug in sorted(approved):
        folder = apps / slug
        if folder.is_symlink():
            raise ValueError(f"Unsafe app folder: {slug}")
        compose = _bytes(folder / "docker-compose.yml")
        _check_compose(compose, slug)
        entries[f"Apps/{slug}/docker-compose.yml"] = compose
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Symlink forbidden in release: {path}")
            if path.is_dir() or path.name == "docker-compose.yml":
                continue
            relative = path.relative_to(folder)
            if path.suffix.lower() not in ASSET_SUFFIXES:
                raise ValueError(f"Unexpected file type in release: {path}")
            entries[f"Apps/{slug}/{relative.as_posix()}"] = _bytes(path)
    if sum(map(len, entries.values())) > MAX_TOTAL:
        raise ValueError("Archive exceeds size budget")
    return entries


def export(source: Path, selection: Path, output: Path) -> int:
    entries = archive_entries(source, selection)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".mrstore-", suffix=".zip",
                                     dir=output.parent, delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(entries.items()):
                item = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                item.compress_type = ZIP_DEFLATED
                item.external_attr = 0o100644 << 16
                archive.writestr(item, data)
        with ZipFile(temporary) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(entries):
                raise ValueError("ZIP integrity verification failed")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return sum(k.endswith("/docker-compose.yml") for k in entries)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True,
                        help="Security-approved release-source, never repository root")
    parser.add_argument("--selection", type=Path, required=True,
                        help="Current release-selection.json produced by eight Trivy shards")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    count = export(options.source, options.selection, options.output)
    print(f"Created preview CasaOS/Homeio ZIP: {count} approved apps; "
          "no unapproved apps included; runtime compatibility NOT certified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
