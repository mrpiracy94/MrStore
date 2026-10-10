"""Offline MrStore storefront/asset audit. Never downloads or executes app assets."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = {"Media", "Productivity", "Home", "Networking", "AI", "Finance",
             "Social", "Developer", "Others"}
SCREENSHOT_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def audit(root: Path = ROOT) -> dict:
    root = Path(root)
    issues = []
    def load(path):
        return json.loads((root / path).read_text(encoding="utf-8"))

    store = load("store-config.json")
    categories = load("category-list.json")
    recommended = load("recommend-list.json")
    featured = load("featured-apps.json")
    names = {item.get("name") for item in categories}
    if names != SUPPORTED or len(categories) != len(SUPPORTED):
        issues.append("Categories must match the nine supported manifest categories")
    if store.get("version") != 2 or store.get("store_id") != "io.github.mrpiracy94.mrstore":
        issues.append("Store v2 identifier must remain stable")
    for locale in ("en_US", "pt_PT"):
        if not store.get("name", {}).get(locale) or not store.get("description", {}).get(locale):
            issues.append(f"Missing store localization {locale}")
    icon = store.get("icon", "")
    if icon != "https://raw.githubusercontent.com/mrpiracy94/MrStore/main/branding/mrstore-icon.svg":
        issues.append("Unexpected or insecure store icon URL")
    icon_path = root / "branding/mrstore-icon.svg"
    try:
        if ET.parse(icon_path).getroot().tag != "{http://www.w3.org/2000/svg}svg":
            issues.append("Store SVG logo is invalid")
    except (OSError, ET.ParseError) as exc:
        issues.append(f"Store SVG logo could not be parsed: {exc}")

    folders = sorted((root / "Apps").glob("*/docker-compose.yml"))
    inventory = {}
    icon_sources = Counter()
    local_screenshots = 0
    for manifest in folders:
        item = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        meta = item.get("x-casaos") or {}
        name = manifest.parent.name
        inventory[name] = meta
        if meta.get("category") not in names:
            issues.append(f"{name}: category missing from store list")
        for field in ("icon", "thumbnail"):
            url = meta.get(field)
            if not isinstance(url, str) or not url.startswith("https://"):
                issues.append(f"{name}: missing HTTPS {field}")
            else:
                icon_sources["local" if "mrpiracy94/MrStore/main/Apps/" in url else "external"] += 1
        for image in manifest.parent.iterdir():
            if image.name.startswith("screenshot-") and image.suffix.lower() in SCREENSHOT_EXTS:
                if image.stat().st_size < 128:
                    issues.append(f"{name}: missing or truncated screenshot asset")
                elif image.suffix.lower() == ".png" and image.open("rb").read(8) != b"\x89PNG\r\n\x1a\n":
                    issues.append(f"{name}: invalid PNG screenshot signature")
                else:
                    local_screenshots += 1

    rec_ids = [item.get("name") for item in recommended]
    featured_ids = [item.get("appid") for item in featured]
    for label, values in (("recommendations", rec_ids), ("featured", featured_ids)):
        if len(values) != len(set(values)):
            issues.append(f"Duplicate {label}")
        for value in values:
            if value not in inventory:
                issues.append(f"{label}: unknown app {value}")
    if not rec_ids or not featured_ids:
        issues.append("Storefront recommendations and featured apps must not be empty")

    local_pt = sum(bool(m.get("description", {}).get("pt_PT"))
                   for m in inventory.values())
    return {
        "apps": len(inventory),
        "categories": len(categories),
        "featured": len(featured_ids),
        "recommended": len(rec_ids),
        "descriptions_pt_PT": local_pt,
        "local_screenshots": local_screenshots,
        "icon_and_thumbnail_sources": dict(icon_sources),
        "errors": issues,
        "note": "External asset HTTP status and real ZimaOS rendering require separate online/runtime checks. No screenshots are fabricated.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    data = audit(args.root)
    output = args.root / "out/branding-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return int(args.strict and bool(data["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
