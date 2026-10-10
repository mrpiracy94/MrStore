"""Fail-closed scan gate for rebuilt Go images, no CVE exemptions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def check(report: dict) -> dict[str, int]:
    if not isinstance(report, dict) or not isinstance(report.get("Results"), list):
        raise ValueError("Trivy report lacks Results array")
    entries = report["Results"]
    if not entries:
        raise ValueError("Trivy Results is empty: scan cannot certify an image")
    counts = {"HIGH": 0, "CRITICAL": 0}
    seen_targets = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("Target"), str) or not entry["Target"].strip():
            raise ValueError("Trivy report has missing or invalid scan target")
        seen_targets.add(entry["Target"])
        vulns = entry.get("Vulnerabilities")
        if vulns is None:
            continue
        if not isinstance(vulns, list):
            raise ValueError("Trivy report has malformed vulnerabilities")
        for hit in vulns:
            if not isinstance(hit, dict) or not isinstance(hit.get("VulnerabilityID"), str):
                raise ValueError("Trivy report has a malformed vulnerability")
            severity = hit.get("Severity")
            if severity not in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}:
                raise ValueError("Trivy vulnerability has a missing severity: " + str(severity))
            if severity in counts:
                counts[severity] += 1
    if not seen_targets:
        raise ValueError("No valid Trivy scan targets")
    if any(counts.values()):
        raise ValueError(f"Blocking release with {counts['CRITICAL']} CRITICAL / {counts['HIGH']} HIGH")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--app", choices=("gitea", "qui"), required=True)
    parser.add_argument("--arch", choices=("amd64", "arm64"), required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    counts = check(report)
    print(f"Approved {args.app} linux/{args.arch}: {counts['CRITICAL']} CRITICAL / {counts['HIGH']} HIGH")


if __name__ == "__main__":
    main()
