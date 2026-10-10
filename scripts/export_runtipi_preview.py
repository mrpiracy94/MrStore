"""Experimental Runtipi v4+ custom store ZIP (source repo seed; real-device tests needed).

Uses the same strict single-service filter as the Umbrel pilot. Import requires
publishing this ZIP's contents in a dedicated GitHub repository, not a ZIP URL.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import yaml
try:
    from export_universal import archive_entries
    from export_umbrel_preview import convert, label
except ImportError:
    from scripts.export_universal import archive_entries
    from scripts.export_umbrel_preview import convert, label

# Neutral MrStore placeholder JPEG. Replace with rights-cleared, verified per-app icons.
LOGO_JPG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDABEMDQ8NCxEPDg8TEhEUGSocGRcXGTQlJx8qPTZBQDw2OzpETGJTREhcSTo7VXRWXGVobW5tQlJ4gHdqf2JrbWn/2wBDARITExkWGTIcHDJpRjtGaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWlpaWn/wAARCAAwADADASIAAhEBAxEB/8QAGQABAAMBAQAAAAAAAAAAAAAABQADBAYC/8QANRAAAQMCAwMHDQEBAAAAAAAAAQIDEQAEBhIhBZHBFjE1QXOx0RMiRFFTYWRygYKSo+EU8f/EABgBAQEBAQEAAAAAAAAAAAAAAAMEBQEC/8QAJREAAQMDAgYDAAAAAAAAAAAAAgABEQMEEhOBFDRBYnGRM1FS/9oADAMBAAIRAxEAPwDW66hhpTrqglCRJJoVzEiAshu2UpPUVLg7oNTE61Bu3bB81RUoj3iI7zQdtbPXTnk2EZ1xMSBp9az7e3BwzNaFeubHgCa5S/Cfs/lTlL8J+z+UPdWdxZlIuG8mbm1BndXq22fdXaCthrOkGCcwGv1p9C3jLp5Qa9eY6+EunEgzDNakJnUhyTG6mLW5au2EvMqlJ5x1g+o1xTzS2HVNOpyrSYImaWwytQvHWwfNU3mI94IjvNFXtqbBkCWhcG54mrsUei/fwrLhzpI9meFasUei/fwrLhzpI9meFeg5X2uHzPpKbSbG0ba4aQJetlyAOc6f93VfZBFn5CwTBWGytZ98jiTuoh+/Vs/bly4E50qgKTMToKs2PdKvNtPPqEZmzAmYEjSiKkWn2xO6Rqg6ndMbI7a/Slx83CteGukHOyPeKybX6UuPm4Vrw10g52R7xVNTl9lMHz7rTihJy2yoOUFQJjSdPA1z9dxdWzV2wpl5MpPMesH1igHMOXIWQ280pPUVSDug0VtXAQxJ4hNc0DI8haZQ1Sl+Tt57Rj8j4VOTt57Rj8j4VTxFL9KbQqfSIpjDST/udVByhogmNJkeBqJw7dZhmdZCZ1IJJjdTlhYtWLHk29VHVazzqNT3FwDg4i8ynt7c2NiJohf/2Q=="
)


def convert_tipi(slug: str, source: dict) -> dict[str, bytes] | None:
    result = convert(slug, source)
    if not result:
        return None
    meta = source["x-casaos"]
    compose = yaml.safe_load(result[1])
    compose["services"].pop("app_proxy")
    main = meta["main"]
    port = source["services"][main]["ports"][0]["target"]
    compose["services"][main]["x-runtipi"] = {
        "is_main": True, "internal_port": int(port)}
    compose.pop("version", None)
    compose["x-runtipi"] = {"schema_version": 2}
    title = label(meta.get("title"), slug)
    tagline = label(meta.get("tagline"), title)
    architecture = meta.get("architectures", [])
    config = {
        "id": slug, "name": title, "description": tagline,
        "short_desc": tagline[:120], "version": str(meta.get("version", "1.0.0")),
        "tipi_version": 1, "min_tipi_version": "4.5.0",
        "available": True, "exposable": True, "dynamic_config": True,
        "port": int(meta["port_map"]), "categories": ["utilities"],
        "author": "MrStore", "source": "https://github.com/mrpiracy94/MrStore",
        "website": "https://github.com/mrpiracy94/MrStore",
        "form_fields": [], "supported_architectures": (
            [a for a in architecture if a in ("amd64", "arm64")] or ["amd64"]),
        "created_at": 0, "updated_at": 0,
    }
    prefix = f"apps/{slug}"
    return {
        f"{prefix}/config.json": (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode(),
        f"{prefix}/docker-compose.yml": yaml.safe_dump(
            compose, sort_keys=False, allow_unicode=True).encode(),
        f"{prefix}/metadata/description.md": (f"# {title}\n\n{tagline}\n").encode(),
        f"{prefix}/metadata/logo.jpg": LOGO_JPG,
    }


def package(source: Path, selection: Path, output: Path) -> dict:
    entries = archive_entries(source, selection)
    slugs = sorted({path.split("/")[1] for path in entries if path.startswith("Apps/")})
    all_files = {}
    excluded = []
    for slug in slugs:
        manifest = entries.get(f"Apps/{slug}/docker-compose.yml")
        converted = convert_tipi(slug, yaml.safe_load(manifest)) if manifest else None
        if converted:
            all_files.update(converted)
        else:
            excluded.append(slug)
    if len(excluded) == len(slugs):
        raise ValueError("No eligible Runtipi app; preview not published")
    if output.exists():
        raise ValueError("Refusing to overwrite Runtipi preview")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".mrstore-preview-", suffix=".zip",
                                     dir=output.parent, delete=False) as temp:
        tmp = Path(temp.name)
    try:
        with ZipFile(tmp, "w", ZIP_DEFLATED) as archive:
            for name, data in sorted(all_files.items()):
                archive.writestr(name, data)
        with ZipFile(tmp) as verified:
            if verified.testzip() is not None:
                raise ValueError("Runtipi preview ZIP failed integrity verification")
        os.replace(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)
    return {"approved_source": len(slugs), "draft_converted": len(slugs) - len(excluded),
            "excluded": excluded, "real_device_tested": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--selection", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(package(args.source, args.selection, args.output),
                     ensure_ascii=False))
