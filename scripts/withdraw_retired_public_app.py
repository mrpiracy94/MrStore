#!/usr/bin/env python3
"""Withdraw obsolete SteamOS from a *legacy* public catalog, without reapproval.

This is a removal-only operation. It cannot publish new apps or invent Trivy
evidence. Refuses to operate on an audited release-status.json catalog.
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

RETIRED = "io.github.mrpiracy94.steamos"
STEAM = "io.github.mrpiracy94.steam"


def read_index(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get("apps"), list):
        raise ValueError(f"Invalid index: {path.name}")
    ids = [item.get("id") if isinstance(item, dict) else None for item in obj["apps"]]
    if not all(isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Missing or duplicate app IDs")
    if "app_count" in obj and obj["app_count"] != len(ids):
        raise ValueError("Invalid original app count")
    if STEAM not in ids:
        raise ValueError("Steam is missing; refusing a broader change")
    return obj


def remove_entry(obj: dict) -> tuple[dict, bool]:
    out = copy.deepcopy(obj)
    count = len(out["apps"])
    out["apps"] = [row for row in out["apps"] if row["id"] != RETIRED]
    if "app_count" in out:
        out["app_count"] = len(out["apps"])
    return out, len(out["apps"]) != count


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def verify_checksum(site: Path) -> None:
    tar = site / "metadata.tar.gz"
    proof = site / "metadata.sha256"
    if not tar.is_file() or not proof.is_file():
        raise ValueError("Missing legacy metadata tar/checksum")
    parts = proof.read_text(encoding="ascii").split()
    if len(parts) != 2 or parts[1] != "metadata.tar.gz" or not re.fullmatch(r"[a-f0-9]{64}", parts[0]):
        raise ValueError("Invalid metadata checksum format")
    if hashlib.sha256(tar.read_bytes()).hexdigest() != parts[0]:
        raise ValueError("Legacy metadata checksum mismatch")


def rewrite_archive(site: Path) -> None:
    tar = site / "metadata.tar.gz"
    temp = site / "metadata.tar.gz.pending"
    entries = []
    removed = 0
    patched = 0
    names = set()
    try:
        with tarfile.open(tar, "r:gz") as original:
            for info in original:
                name = info.name.removeprefix("./").rstrip("/")
                if name.startswith("/") or ".." in Path(name).parts or name in names:
                    raise ValueError("Unsafe/duplicate archive path: " + name)
                names.add(name)
                if RETIRED in name.split("/"):
                    removed += 1
                    continue
                if not (info.isfile() or info.isdir()):
                    raise ValueError("Unknown archive member type: " + name)
                data = original.extractfile(info).read() if info.isfile() else None
                if data is not None and name in ("index.json", "index.pt_PT.json"):
                    idx = json.loads(data)
                    if not isinstance(idx, dict) or not isinstance(idx.get("apps"), list):
                        raise ValueError("Invalid archived index")
                    updated, changed = remove_entry(idx)
                    if changed:
                        data = json_bytes(updated)
                        info.size = len(data)
                        patched += 1
                elif data is not None and RETIRED.encode() in data:
                    raise ValueError("Unsupported SteamOS reference in archive: " + name)
                entries.append((info, data))
        if not (removed or patched):
            raise ValueError("No SteamOS found inside metadata archive; manual review required")
        with temp.open("wb") as dest:
            with gzip.GzipFile(fileobj=dest, mode="wb", filename="", mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as rebuilt:
                    for info, data in entries:
                        rebuilt.addfile(info, io.BytesIO(data) if data is not None else None)
        with tarfile.open(temp, "r:gz") as check:
            for info in check:
                if RETIRED in info.name:
                    raise ValueError("Retired app survived archive rewrite")
                if info.isfile() and info.name.removeprefix("./") in ("index.json", "index.pt_PT.json"):
                    index = json.load(check.extractfile(info))
                    if any(item.get("id") == RETIRED for item in index.get("apps", [])):
                        raise ValueError("Retired entry survived archived index")
        temp.replace(tar)
        (site / "metadata.sha256").write_text(
            hashlib.sha256(tar.read_bytes()).hexdigest() + "  metadata.tar.gz\n", encoding="ascii")
    finally:
        temp.unlink(missing_ok=True)


def withdraw(site: Path, source: Path) -> dict:
    if (source / "Apps/steamos/docker-compose.yml").exists():
        raise ValueError("Cannot withdraw while SteamOS exists in main")
    if not (source / "Apps/steam/docker-compose.yml").is_file():
        raise ValueError("Steam is absent from main")
    if (site / "release-status.json").exists():
        raise ValueError("Audited catalog present: manual rewrite of security proof forbidden")
    primary = read_index(site / "index.json")
    pt = read_index(site / "index.pt_PT.json")
    ids = {a["id"] for a in primary["apps"]}
    if ids != {a["id"] for a in pt["apps"]}:
        raise ValueError("Main and Portuguese indexes disagree")
    folder = site / "apps" / RETIRED
    if RETIRED not in ids:
        if folder.exists():
            raise ValueError("Orphaned retired app folder")
        return {"changed": False, "app_count": len(ids)}
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("Cannot find a safe SteamOS app folder")
    verify_checksum(site)
    updated, _ = remove_entry(primary)
    updated_pt, _ = remove_entry(pt)
    if len(updated["apps"]) != len(primary["apps"]) - 1:
        raise ValueError("Expected exactly one retired app")
    rewrite_archive(site)
    (site / "index.json").write_bytes(json_bytes(updated))
    (site / "index.pt_PT.json").write_bytes(json_bytes(updated_pt))
    shutil.rmtree(folder)
    verify_checksum(site)
    assert RETIRED not in {r["id"] for r in read_index(site / "index.json")["apps"]}
    assert STEAM in {r["id"] for r in read_index(site / "index.json")["apps"]}
    return {"changed": True, "app_count": len(updated["apps"]),
            "removed": RETIRED, "security_release_approved": False}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--site", required=True, type=Path)
    p.add_argument("--source", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(withdraw(args.site, args.source), indent=2))


if __name__ == "__main__":
    main()
