"""Summarise *format eligibility*, never claim installations or upgrades were tested.

Consumes only a security-approved release selection and optional artifacts
generated in the same GitHub Actions run. A missing optional export is
reported as unavailable, not silently replaced by an unsafe source ZIP.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

PROFILES = (
    ("zimaos", "ZimaOS", "v2_catalog"),
    ("homeio", "Homeio", "casaos_zip_preview"),
    ("casaos", "CasaOS", "casaos_zip_preview"),
    ("umbrelos", "umbrelOS", "umbrel_git_seed"),
    ("cosmos", "Cosmos", "compose_import"),
    ("portainer", "Portainer", "compose_and_templates"),
    ("homedock", "HomeDock OS", "hds_hdstore_preview"),
    ("olares", "Olares", "oac_helm_preview"),
    ("dockge", "Dockge", "compose_import"),
    ("runtipi", "Runtipi", "runtipi_git_seed"),
    ("docker-linux", "Docker / Linux", "compose_cli"),
)


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON document: {path}")
    return data


def _archive_apps(path: Path, marker: str, kind: str) -> set[str] | None:
    if not path.is_file():
        return None
    with ZipFile(path) as z:
        entries = z.namelist()
        if z.testzip() is not None:
            raise ValueError(f"Corrupt {kind} archive")
        if kind == "homeio":
            found = {name.split("/")[1] for name in entries
                     if name.startswith("Apps/") and name.endswith("/docker-compose.yml")
                     and name.count("/") == 2}
        elif kind == "umbrel":
            found = {name[len("mrstore-"):-len("/umbrel-app.yml")]
                     for name in entries
                     if name.startswith("mrstore-") and name.endswith("/umbrel-app.yml")
                     and name.count("/") == 1}
        else:
            found = {name.split("/")[1] for name in entries
                     if name.startswith("apps/") and name.endswith("/config.json")
                     and name.count("/") == 2}
        if not found:
            raise ValueError(f"Empty {kind} archive")
        return found


def _subset(name: str, values: set[str], approved: set[str]) -> set[str]:
    if not values.issubset(approved):
        raise ValueError(f"{name} lists an app outside the approved release")
    return values


def report(selection: Path, dist: Path) -> dict:
    release = _read_json(selection)
    slugs = release.get("approved")
    if (not isinstance(slugs, list) or not slugs or
            release.get("approved_count") != len(slugs) or
            any(not isinstance(s, str) for s in slugs) or
            len(set(slugs)) != len(slugs)):
        raise ValueError("Missing or invalid security approval selection")
    approved = set(slugs)

    # Required approved catalog and Compose by every listed app.
    catalog = _read_json(dist / "universal" / "catalog.json")
    if catalog.get("approved_count") != len(slugs):
        raise ValueError("Universal catalog count mismatch")
    apps = catalog.get("apps")
    if not isinstance(apps, list) or set(
            app.get("slug") for app in apps if isinstance(app, dict)) != approved:
        raise ValueError("Portable catalog differs from approved app set")
    for slug in approved:
        if not (dist / "universal" / "compose" / (slug + ".yml")).is_file():
            raise ValueError(f"Missing audited Compose manifest: {slug}")

    def optional_catalog(path: Path, key: str, field: str) -> set[str] | None:
        if not path.is_file():
            return None
        info = _read_json(path)
        if info.get("source_approved") != len(slugs):
            raise ValueError(f"{key}: stale release selection")
        items = info.get(field)
        if not isinstance(items, list):
            raise ValueError(f"{key}: invalid app records")
        return _subset(key, {item["slug"] for item in items}, approved)

    zip_apps = _archive_apps(dist / "store/casaos-homeio-preview.zip", "Apps", "homeio")
    if zip_apps is not None and zip_apps != approved:
        raise ValueError("CasaOS/Homeio ZIP differs from approved release")

    umbrel = _archive_apps(dist / "store/umbrel-community-preview.zip", "umbrel", "umbrel")
    runtipi = _archive_apps(dist / "store/runtipi-store-preview.zip", "runtipi", "runtipi")
    for name, items in (("umbrel", umbrel), ("runtipi", runtipi)):
        if items is not None:
            _subset(name, items, approved)

    homedock = optional_catalog(dist / "homedock/catalog.json", "homedock", "packages")
    olares = optional_catalog(dist / "olares/catalog.json", "olares", "packages")

    templates = dist / "universal/portainer-templates.json"
    if templates.is_file():
        data = _read_json(templates)
        if data.get("version") != "2" or not isinstance(data.get("templates"), list):
            raise ValueError("Invalid Portainer templates v2")
        portainer = _subset("portainer", {item["name"] for item in data["templates"]},
                            approved)
    else:
        portainer = set()

    source = {
        "zimaos": approved,
        "homeio": zip_apps or set(),
        "casaos": zip_apps or set(),
        "umbrelos": umbrel or set(),
        "cosmos": approved,
        "portainer": approved,
        "homedock": homedock or set(),
        "olares": olares or set(),
        "dockge": approved,
        "runtipi": runtipi or set(),
        "docker-linux": approved,
    }
    systems = []
    for ident, name, kind in PROFILES:
        eligible = source[ident]
        systems.append({
            "id": ident, "name": name, "method": kind,
            "format_eligible_count": len(eligible),
            "format_eligible_apps": sorted(eligible),
            "runtime_verified_count": 0,
            "upgrade_verified_count": 0,
            "native_certified": False,
            "status": "generated_unverified" if eligible else "not_generated",
        })
    return {
        "version": 1, "security_selection_count": len(slugs),
        "source": "release-selection.json", "runtime_tested": False,
        "portainer_single_container_template_count": len(portainer),
        "systems": systems,
        "warning": "Format eligibility != installability. No real device or upgrade evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.selection, args.dist)
    target = args.dist / "universal/support-report.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("Compatibility formats:", ", ".join(
        f"{s['name']}={s['format_eligible_count']}"
        for s in result["systems"]) + " (runtime verified: zero)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
