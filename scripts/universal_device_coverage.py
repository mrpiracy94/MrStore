"""Real-device evidence inventory for MrStore Universal.

A claim backed by a GitHub issue/PR remains community-reported, NOT an
independent vendor certification. Changes to Compose invalidate old results.
Never infer results from CVE scans, synthetic fixtures, or file formats.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

import yaml

PLATFORMS = (
    "umbrelos", "homeio", "casaos", "zimaos", "cosmos", "portainer",
    "homedock", "olares", "dockge", "runtipi", "docker-linux",
)
CHECKS = (
    "native_import", "installed_on_target", "core_function",
    "restart_persistence", "upgrade", "backup_restore", "rollback",
    "security_review",
)
C2 = ("native_import", "installed_on_target")
C3 = C2 + ("core_function", "restart_persistence")
C4 = CHECKS
FIELDS = {
    "app", "platform", "platform_version", "architecture", "tested_at",
    "compose_sha256", "evidence_url", "checks", "reviewed_by",
}
EVIDENCE = re.compile(
    r"^https://github\.com/mrpiracy94/MrStore/(?:issues|pull)/[1-9]\d*(?:#[\w-]+)?$"
)
HANDLE = re.compile(r"^[A-Za-z\d](?:[A-Za-z\d-]{0,37})$")
HEX = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_\- ]{0,79}$")


def _level(record: dict) -> str | None:
    checks = record["checks"]
    if all(checks[k] is True for k in C4):
        return "C4"
    if all(checks[k] is True for k in C3):
        return "C3"
    if all(checks[k] is True for k in C2):
        return "C2"
    return None


def _read(root: Path, source: Path | None = None) -> list[dict]:
    data = json.loads((source or root / "data/universal-device-tests.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema", "description", "tests"}:
        raise ValueError("Invalid device evidence registry structure")
    if type(data["schema"]) is not int or data["schema"] != 1 or not isinstance(data["tests"], list):
        raise ValueError("Invalid device evidence schema or tests")
    return data["tests"]


def inventory(root: Path, source: Path | None = None) -> dict:
    root = Path(root)
    records = _read(root, source)
    apps_root = root / "Apps"
    catalog = {}
    for app in apps_root.iterdir():
        path = app / "docker-compose.yml"
        if not app.is_dir() or not path.is_file() or path.is_symlink():
            continue
        # This SHA is content-addressed. Any manifest change invalidates evidence.
        info = yaml.safe_load(path.read_text(encoding="utf-8"))
        architectures = (info.get("x-casaos", {}).get("architectures", [])
                         if isinstance(info, dict) else [])
        if not isinstance(architectures, list):
            raise ValueError(f"{app.name}: invalid declared architectures")
        catalog[app.name] = {
            "sha": hashlib.sha256(path.read_bytes()).hexdigest(),
            "architectures": set(arch for arch in architectures if arch in ("amd64", "arm64")),
        }
    by_target = {name: {"C2": set(), "C3": set(), "C4": set()} for name in PLATFORMS}
    stale = 0
    valid = 0
    indexed = set()
    for i, item in enumerate(records):
        where = f"tests[{i}]"
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError(f"{where}: fields must match approved evidence schema")
        if item["app"] not in catalog or item["platform"] not in PLATFORMS:
            raise ValueError(f"{where}: unknown app or platform")
        if item["architecture"] not in ("amd64", "arm64"):
            raise ValueError(f"{where}: unsupported CPU architecture")
        if not isinstance(item["platform_version"], str) or not VERSION.fullmatch(item["platform_version"]):
            raise ValueError(f"{where}: invalid platform version")
        try:
            tested = date.fromisoformat(item["tested_at"])
        except (TypeError, ValueError):
            raise ValueError(f"{where}: invalid test date") from None
        if tested.isoformat() != item["tested_at"] or tested > date.today():
            raise ValueError(f"{where}: invalid or future test date")
        if not isinstance(item["compose_sha256"], str) or not HEX.fullmatch(item["compose_sha256"]):
            raise ValueError(f"{where}: invalid Compose hash")
        if not isinstance(item["evidence_url"], str) or not EVIDENCE.fullmatch(item["evidence_url"]):
            raise ValueError(f"{where}: issue/PR link required")
        reviews = item["reviewed_by"]
        if (not isinstance(reviews, list) or len(reviews) != 2 or
                not all(isinstance(x, str) and HANDLE.fullmatch(x) for x in reviews) or
                reviews[0].lower() == reviews[1].lower()):
            raise ValueError(f"{where}: two distinct recorded reviewers required")
        checks = item["checks"]
        if not isinstance(checks, dict) or set(checks) != set(CHECKS) or any(type(v) is not bool for v in checks.values()):
            raise ValueError(f"{where}: missing/non-boolean checks")
        key = (item["app"], item["platform"], item["architecture"], item["platform_version"])
        if key in indexed:
            raise ValueError(f"{where}: duplicated device evidence record")
        indexed.add(key)
        if item["compose_sha256"] != catalog[item["app"]]["sha"] or item["architecture"] not in catalog[item["app"]]["architectures"]:
            stale += 1
            continue
        valid += 1
        level = _level(item)
        if level:
            levels = {"C2": ("C2",), "C3": ("C2", "C3"), "C4": ("C2", "C3", "C4")}[level]
            for v in levels:
                by_target[item["platform"]][v].add((item["app"], item["architecture"]))
    required = {(app, arch) for app, meta in catalog.items()
                for arch in meta["architectures"]}
    full_coverage = bool(required) and all(
        required.issubset(by_target[name]["C4"]) for name in PLATFORMS)
    return {
        "schema": 1,
        "method": "community_reviewed_device_reports_not_vendor_certification",
        "total_source_apps": len(catalog),
        "total_recorded_tests": len(records),
        "current_evidence_records": valid,
        "stale_records": stale,
        "platforms": [
            {
                "id": name,
                "c2_device_app_arch_pairs": len(by_target[name]["C2"]),
                "c3_functional_app_arch_pairs": len(by_target[name]["C3"]),
                "c4_upgrade_restore_app_arch_pairs": len(by_target[name]["C4"]),
                "c4_apps": sorted({app for app, _ in by_target[name]["C4"]}),
                "vendor_certified": False,
            }
            for name in PLATFORMS
        ],
        "all_eleven_have_c4_evidence": all(by_target[name]["C4"] for name in PLATFORMS),
        "all_254_apps_certified_everywhere": len(catalog) == 254 and full_coverage,
        "all_declared_architectures_c4_everywhere": full_coverage,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--registry", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = inventory(args.root, args.registry)
    output = args.output or args.root / "out/universal-device-coverage.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Device tests: {result['current_evidence_records']} current, "
          f"{result['stale_records']} stale; platforms with C4: "
          f"{sum(s['c4_upgrade_restore_app_arch_pairs'] > 0 for s in result['platforms'])}/11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
