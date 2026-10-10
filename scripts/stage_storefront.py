"""Stage only a static, no-network-code storefront atop an approved ZimaOS v2 release.

Never alter the official index.json, store.json or app manifests.
Fail closed without an exact approved index and release selection report.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ("index.html", "assets/site.css", "assets/site.js",
           "assets/mark.svg", "assets/readme-banner.svg")
PREFIX = "io.github.mrpiracy94."


def verify_release(dist: Path) -> int:
    for name in ("index.json", "store.json", "release-status.json"):
        if not (dist / name).is_file():
            raise ValueError("Cannot stage storefront: missing approved release " + name)
    store = json.loads((dist / "store.json").read_text(encoding="utf-8"))
    index = json.loads((dist / "index.json").read_text(encoding="utf-8"))
    release = json.loads((dist / "release-status.json").read_text(encoding="utf-8"))
    if store.get("version") != 2 or index.get("version") != 2:
        raise ValueError("Not a ZimaOS v2 release")
    entries = index.get("apps")
    approved = release.get("approved")
    if not isinstance(entries, list) or not isinstance(approved, list):
        raise ValueError("Missing release app set")
    count = release.get("approved_count")
    if (type(count) is not int or count < 1 or count != len(entries) or
            count != len(approved) or index.get("app_count") != count):
        raise ValueError("Inconsistent approved release counts")
    app_ids = {app.get("id") for app in entries if isinstance(app, dict)}
    expected = {PREFIX + slug for slug in approved if isinstance(slug, str)}
    if len(app_ids) != count or len(expected) != count or app_ids != expected:
        raise ValueError("Published app IDs do not match the approved release list")
    return count


def stage(source: Path, dist: Path) -> int:
    source = Path(source)
    dist = Path(dist)
    count = verify_release(dist)
    for relative in ALLOWED:
        src, dest = source / relative, dist / relative
        if not src.is_file() or src.is_symlink():
            raise ValueError("Missing or unsafe storefront asset: " + str(src))
        if dest.exists():
            raise ValueError("Refusing to overwrite build output: " + str(dest))
        if src.stat().st_size > 250_000:
            raise ValueError("Storefront asset unexpectedly large: " + str(src))
    for relative in ALLOWED:
        dest = dist / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, dest)
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "web")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    count = stage(args.source, args.dist)
    print("Informational storefront added beside " + str(count) +
          " approved ZimaOS apps; official JSON and Compose files unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
