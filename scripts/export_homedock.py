"""HomeDock OS HDS 1.0 exporter, independently implemented from public format docs.

Builds .hds packages and .hdstore bundle ONLY from the security-approved
release-source; uses SHA256 *integrity checks*, NOT publisher authenticity.
HomeDock real-device install/upgrade remains unverified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import zlib
import yaml

try:
    from export_universal import archive_entries
except ImportError:
    from scripts.export_universal import archive_entries

VERSION = "1.0"
MAX_HDS = 5 * 1024 * 1024
MAX_HDSTORE = 75 * 1024 * 1024
CATEGORIES = {
    "Media": "Media", "Productivity": "Files & Productivity",
    "Home": "Home & Automation", "Networking": "Networking",
    "Network": "Networking", "Developer": "Developer Tools",
    "AI": "AI", "Games": "Gaming", "Social": "Social",
    "Cloud": "Files & Productivity", "Utilities": "Developer Tools",
}


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(
        ">I", zlib.crc32(kind + data) & 0xffffffff)


def brand_icon() -> bytes:
    """Small local orange PNG logo. No external fetches or dependencies."""
    n = 96
    glyph = ("11000011", "11100111", "11111111", "11011011",
             "11000011", "11000011", "11000011")
    rows = []
    for y in range(n):
        line = bytearray([0])
        for x in range(n):
            inside = 16 <= x < 80 and 20 <= y < 76
            if inside and glyph[min(6, (y - 20) * 7 // 56)][min(7, (x - 16) // 8)] == "1":
                line.extend((24, 25, 31, 255))
            elif 7 <= x < 89 and 7 <= y < 89:
                line.extend((255, 131, 31, 255))
            else:
                line.extend((16, 18, 23, 255))
        rows.append(bytes(line))
    body = zlib.compress(b"".join(rows), 9)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0)) +
            _chunk(b"IDAT", body) + _chunk(b"IEND", b""))


def pack_zip(items: dict[str, bytes]) -> bytes:
    """Stable ZIP ordering, no external attributes, no executable payloads."""
    out = io.BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED, compresslevel=9) as z:
        for filename in sorted(items):
            if "/" in filename and (filename.startswith("/") or ".." in filename.split("/")):
                raise ValueError("Invalid ZIP path")
            item = ZipInfo(filename, (1980, 1, 1, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            z.writestr(item, items[filename])
    return out.getvalue()


def _name(value, fallback: str) -> str:
    if isinstance(value, dict):
        value = value.get("pt_PT") or value.get("en_US")
    return str(value).strip() if isinstance(value, str) and value.strip() else fallback


def make_hds(slug: str, compose: bytes) -> tuple[bytes, dict]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Unsafe HDS slug")
    definition = yaml.safe_load(compose)
    meta = definition.get("x-casaos", {})
    services = definition.get("services", {})
    main = meta.get("main")
    if (not isinstance(meta, dict) or not isinstance(services, dict)
            or not services or main not in services):
        raise ValueError(f"{slug}: missing main service")
    manifest = {
        "name": slug, "display_name": _name(meta.get("title"), slug),
        "category": CATEGORIES.get(meta.get("category"), "Developer Tools"),
        "type": "Application",
        "description": _name(meta.get("description"), _name(meta.get("tagline"), slug)),
        "docker_image": services[main]["image"],
        "icon": "icon.png",
        "author": "MrStore",
        "version": str(meta.get("version") or "1.0.0"),
        "hds_version": VERSION,
        "dependencies": sorted(s for s in services if s != main),
        "is_group": len(services) > 1,
        "is_new": False,
        "new_until": False,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    png = brand_icon()
    signature = hashlib.sha256(manifest_bytes + png + compose).hexdigest().encode("ascii")
    parts = {"manifest.json": manifest_bytes, "icon.png": png,
             "docker-compose.yml": compose, ".hds_signature": signature}
    package = pack_zip(parts)
    if len(package) > MAX_HDS:
        raise ValueError(f"{slug}: package exceeds 5 MB")
    validate_hds(package)
    return package, manifest


def validate_hds(package: bytes) -> dict:
    with ZipFile(io.BytesIO(package)) as z:
        required = {"manifest.json", "icon.png", "docker-compose.yml", ".hds_signature"}
        if set(z.namelist()) != required or z.testzip() is not None:
            raise ValueError("Incorrect/corrupted HDS archive")
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("hds_version") != VERSION:
            raise ValueError("Unsupported HDS version")
        digest = hashlib.sha256(z.read("manifest.json") + z.read("icon.png") +
                                 z.read("docker-compose.yml")).hexdigest()
        if z.read(".hds_signature").decode("ascii").strip() != digest:
            raise ValueError("Invalid HDS integrity signature")
        return manifest


def build(source: Path, selection: Path, output: Path) -> dict:
    entries = archive_entries(source, selection)
    selected = json.loads(selection.read_text(encoding="utf-8"))
    slugs = selected["approved"]
    if output.exists():
        raise ValueError("Refusing to replace an existing HomeDock export")
    output.mkdir(parents=True)
    manifest_list = []
    files: dict[str, bytes] = {}
    exclusions = {}
    try:
        for slug in sorted(slugs):
            raw = entries[f"Apps/{slug}/docker-compose.yml"]
            try:
                package, manifest = make_hds(slug, raw)
            except ValueError as exc:
                exclusions[slug] = str(exc)
                continue
            filename = slug + ".hds"
            files[filename] = package
            manifest_list.append({
                "filename": filename, "name": slug,
                "display_name": manifest["display_name"],
                "version": manifest["version"],
                "author": manifest["author"],
                "category": manifest["category"],
            })
        if not files:
            raise ValueError("No eligible HDS packages")
        store_manifest = {
            "hdstore_version": VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "package_count": len(manifest_list),
            "packages": manifest_list,
        }
        store_data = json.dumps(store_manifest, ensure_ascii=False, indent=2).encode("utf-8")
        store_sig = hashlib.sha256(store_data + b"".join(
            files[x["filename"]] for x in manifest_list)).hexdigest().encode("ascii")
        bundle = pack_zip({
            "store_manifest.json": store_data,
            **{"packages/" + k: v for k, v in files.items()},
            ".hdstore_signature": store_sig
        })
        if len(bundle) > MAX_HDSTORE:
            raise ValueError("HomeDock bundle exceeds 75MB; split into smaller releases")
        with ZipFile(io.BytesIO(bundle)) as zipped:
            if zipped.testzip() is not None:
                raise ValueError("Corrupt HDStore ZIP")
        for name, content in files.items():
            (output / name).write_bytes(content)
        (output / "mrstore.hdstore").write_bytes(bundle)
        report = {
            "version": 1, "source_approved": len(slugs),
            "exported_count": len(files), "excluded": exclusions,
            "packages": [{"slug": k[:-4], "url": "homedock/" + k} for k in sorted(files)],
            "bundle": "homedock/mrstore.hdstore",
            "runtime_verified": False,
            "integrity_check_only": True,
        }
        (output / "catalog.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    except Exception:
        for file in output.iterdir():
            if file.is_file():
                file.unlink()
        output.rmdir()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    data = build(args.source, args.selection, args.dist / "homedock")
    print(f"HomeDock HDS 1.0: {data['exported_count']}/{data['source_approved']} packages; "
          "integrity verified, real-device installation not verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
