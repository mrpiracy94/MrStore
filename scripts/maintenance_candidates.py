"""Evidence-only dual-architecture CVE comparisons for issue #64.

Never mutates Compose, runs containers, waives CVEs or auto-approves forks.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from catalog import ROOT, apps
from cves import scan
from release_scan import resolve_digest

CANDIDATES = {
    "organizr": [
        ("ghcr.io/organizr/organizr:latest", "official-alternate-registry"),
        ("anguy079/organizr:v2.7.2", "third-party-unverified-fork"),
    ],
    "series-troxide": [],
    "dockge": [
        ("louislam/dockge:nightly", "upstream-unstable-prerelease"),
    ],
}


def compare(app, resolver=resolve_digest, scanner=scan):
    if app.folder not in CANDIDATES:
        raise ValueError("Unsupported app for maintenance comparison")
    if len(app.source["services"]) != 1:
        raise ValueError("Manual review needed for multi-service app")
    (service,) = app.source["services"].values()
    current = service["image"]
    platforms = sorted(set(app.metadata.get("architectures") or []))
    if not platforms or any(p not in ("amd64", "arm64") for p in platforms):
        raise ValueError("Missing/unsupported architectures")
    cases = [(current, "current-manifest")] + CANDIDATES[app.folder]
    evidence = []
    for image, category in cases:
        try:
            pinned, error = resolver(image)
        except Exception as exc:
            pinned, error = None, "registry lookup exception: " + type(exc).__name__
        scans = {}
        if pinned and not error:
            for platform in platforms:
                try:
                    findings, failure = scanner(pinned, platform=platform)
                except Exception as exc:
                    findings, failure = [], "scanner exception: " + type(exc).__name__
                if not isinstance(findings, list):
                    findings, failure = [], "scanner response invalid"
                high = sum(isinstance(x, dict) and x.get("severity") == "HIGH"
                           for x in findings)
                critical = sum(isinstance(x, dict) and x.get("severity") == "CRITICAL"
                               for x in findings)
                scans[platform] = {"status": "error" if failure else "ok",
                                   "error": failure, "high": high, "critical": critical}
        if error or not pinned or set(scans) != set(platforms) or any(
            value["status"] != "ok" for value in scans.values()
        ):
            result = "inconclusive"
        elif any(value["high"] or value["critical"] for value in scans.values()):
            result = "vulnerable"
        else:
            result = "no_high_or_critical_detected"
        evidence.append({
            "image": image, "candidate_type": category,
            "pinned_digest_ref": pinned, "digest_error": error,
            "platforms": platforms, "scans": scans, "scan_result": result,
            "automatically_approved": False, "compatibility_verified": False,
            "trusted_source_verified": False, "upstream_maintenance_verified": False,
        })
        print(f"{app.folder}: {image}: {result}", flush=True)
    return {
        "schema": 1, "app": app.folder,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_image": current, "declared_architectures": platforms,
        "evidence": evidence, "any_automatically_approved": False,
        "catalog_mutated": False,
        "note": ("Zero detected HIGH/CRITICAL does not approve registry migrations, "
                 "third-party forks or prerelease tags; runtime/trust review required."),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--app", choices=sorted(CANDIDATES), required=True)
    p.add_argument("--output", type=Path, default=None)
    opts = p.parse_args()
    target = next((item for item in apps() if item.folder == opts.app), None)
    if target is None:
        p.error("Target app not found")
    report = compare(target)
    dest = opts.output or ROOT / "out" / f"maintenance-{opts.app}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
