"""Fail release if the built ZimaOS v2 files lose mandatory secret guards.

Static generated-payload test only; does NOT check the device installer UI.
Never print secret values and never start containers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import yaml

from catalog import ROOT
from check_required_secrets import REQUIRED_RE, required_by_app


def _required_in_environment(services: dict) -> set[str]:
    variables = set()
    for spec in services.values():
        if not isinstance(spec, dict):
            continue
        raw = spec.get("environment") or []
        env = raw.values() if isinstance(raw, dict) else raw
        for entry in env:
            variables.update(REQUIRED_RE.findall(str(entry)))
            if "CHANGE_ME" in str(entry):
                raise ValueError("Unconfigured CHANGE_ME in published service")
    return variables


def inspect_built(root: Path = ROOT, dist: Path | None = None) -> dict:
    root = Path(root)
    dist = Path(dist) if dist else root / "dist"
    required = required_by_app(root)
    results = []
    for app_name, variables in sorted(required.items()):
        raw = yaml.safe_load((root / "Apps" / app_name / "docker-compose.yml").read_text())
        app_id = raw["x-casaos"]["id"]
        folder = dist / "apps" / app_id
        errors = []
        compose = folder / "docker-compose.yml"
        meta = folder / "meta.json"
        try:
            built = yaml.safe_load(compose.read_text(encoding="utf-8"))
            got = _required_in_environment(built.get("services") or {})
            if got != set(variables):
                errors.append("required environment expressions are missing or altered")
            if any("x-casaos" in spec for spec in (built.get("services") or {}).values()
                   if isinstance(spec, dict)):
                errors.append("unexpected service-level x-casaos data in v2")
        except (OSError, ValueError, yaml.YAMLError, AttributeError) as exc:
            errors.append("built Compose unreadable: " + type(exc).__name__)
        try:
            built_meta = json.loads(meta.read_text(encoding="utf-8"))
            tip = built_meta.get("tips", {}).get("before_install", "")
            if not isinstance(tip, str) or not all(variable in tip for variable in variables):
                errors.append("required secret setup warning missing from built metadata")
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            errors.append("built metadata unreadable: " + type(exc).__name__)
        results.append({"app": app_name, "ok": not errors, "errors": errors})
    return {"scope": "generated_v2_payload_only", "zimaos_runtime_verified": False,
            "apps": len(results), "passed": sum(x["ok"] for x in results),
            "failed": sum(not x["ok"] for x in results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path, default=None)
    args = parser.parse_args()
    results = inspect_built(args.root, args.dist)
    print(f"ZimaOS v2 secure payload: {results['passed']}/{results['apps']} pass; "
          f"{results['failed']} fail; runtime not verified")
    for item in results["results"]:
        if not item["ok"]:
            print(item["app"] + ": " + "; ".join(item["errors"]))
    return 1 if results["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
