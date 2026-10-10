#!/usr/bin/env python3
"""MrStore: A-Z per-application CVE evidence inventory (report-only).

Consumes existing Trivy release-cves-shard-N.json. Never pulls images, deploys,
closes issues, weakens the release gate, or equates missing scans with clean.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import re
import sys

from catalog import ROOT, apps, image_usage
from cves import shard_images
from release_scan import image_platforms

PINNED = re.compile(r"@sha256:[a-f0-9]{64}$")
VALID_ARCHES = {"amd64", "arm64"}


def inspect_shard(report: dict, shard: int, usage: dict,
                  platforms: dict) -> dict[str, dict]:
    """Reject incomplete or inconsistent shards, rather than trusting a subset."""
    expected = set(shard_images(usage, shard, 8))
    rows = report.get("results")
    if not (report.get("shard") == shard and report.get("shards") == 8
            and report.get("images_total") == len(usage)
            and isinstance(rows, list) and report.get("images_checked") == len(rows)):
        raise ValueError("Invalid shard metadata")
    names = [row.get("image") for row in rows if isinstance(row, dict)]
    if len(names) != len(rows) or len(set(names)) != len(names) or set(names) != expected:
        raise ValueError("Missing, extra or duplicate image evidence")
    result = {}
    for row in rows:
        image = row["image"]
        wanted = platforms[image]
        if row.get("platforms") != wanted:
            raise ValueError("Architecture declarations do not match " + image)
        scans = row.get("scans")
        if not isinstance(scans, dict) or set(scans) not in (set(), set(wanted)):
            raise ValueError("Malformed per-architecture scan: " + image)
        counts = {"critical": 0, "high": 0}
        identifiers = set()
        has_error = bool(row.get("error"))
        for arch, scan in scans.items():
            if not isinstance(scan, dict) or scan.get("status") not in ("ok", "error"):
                raise ValueError("Invalid Trivy status: " + image)
            if type(scan.get("critical")) is not int or type(scan.get("high")) is not int:
                raise ValueError("Missing CVE counts: " + image)
            if scan["critical"] < 0 or scan["high"] < 0:
                raise ValueError("Negative CVE counts: " + image)
            counts["critical"] += scan["critical"]
            counts["high"] += scan["high"]
            has_error = has_error or scan["status"] == "error" or bool(scan.get("error"))
            findings = scan.get("findings", [])
            if not isinstance(findings, list):
                raise ValueError("Malformed findings: " + image)
            count_by_severity = {"HIGH": 0, "CRITICAL": 0}
            for item in findings:
                if not isinstance(item, dict):
                    raise ValueError("Malformed CVE entry: " + image)
                severity = item.get("severity")
                if severity in count_by_severity:
                    count_by_severity[severity] += 1
                    if item.get("cve"):
                        identifiers.add(item["cve"])
            if (count_by_severity["HIGH"] != scan["high"]
                    or count_by_severity["CRITICAL"] != scan["critical"]):
                raise ValueError("CVE totals differ from findings: " + image)
        pinned = row.get("pinned")
        pinned_ok = (isinstance(pinned, str) and bool(PINNED.search(pinned))
                     and pinned.split("@sha256:", 1)[0] == image.split("@sha256:", 1)[0]
                     and ("@sha256:" not in image or pinned == image))
        covered = bool(pinned_ok and set(scans) == set(wanted) and not has_error)
        # Evidence containing vulnerabilities cannot be marked clean even when
        # the producer mislabeled it.
        status = ("VULNERABLE" if counts["critical"] or counts["high"] else
                  "SCANNER_ERROR" if not covered else "CLEAN_OBSERVED")
        if status == "CLEAN_OBSERVED" and row.get("status") != "clean":
            raise ValueError("Contradictory clean evidence: " + image)
        if status == "VULNERABLE" and row.get("status") not in ("vulnerable", "error"):
            raise ValueError("Contradictory vulnerable evidence: " + image)
        result[image] = {"status": status, "critical": counts["critical"],
                         "high": counts["high"], "cves": sorted(identifiers),
                         "architectures": wanted, "digest": pinned if pinned_ok else None}
    return result


def load_evidence(directory: Path, usage: dict, platforms: dict):
    evidence = {}
    warnings = []
    for shard in range(8):
        files = list(directory.rglob(f"release-cves-shard-{shard}.json"))
        if len(files) != 1:
            warnings.append(f"Shard {shard}: expected exactly one report, found {len(files)}")
            continue
        try:
            document = json.loads(files[0].read_text(encoding="utf-8"))
            result = inspect_shard(document, shard, usage, platforms)
        except (ValueError, OSError, TypeError, KeyError) as exc:
            warnings.append(f"Shard {shard}: evidence rejected ({exc})")
            continue
        for image, data in result.items():
            if image in evidence:
                raise ValueError("Image present in multiple shards: " + image)
            evidence[image] = data
    return evidence, warnings


def make_report(items: list, evidence: dict, warnings: list,
                source_sha: str = "") -> dict:
    rows = []
    for app in sorted(items, key=lambda obj: obj.folder.casefold()):
        image_refs = sorted({service["image"] for service in
                             app.source["services"].values()
                             if isinstance(service, dict) and isinstance(service.get("image"), str)})
        observed = [evidence.get(image) for image in image_refs]
        vulnerable = any(entry and entry["status"] == "VULNERABLE" for entry in observed)
        bad_scan = any(entry and entry["status"] == "SCANNER_ERROR" for entry in observed)
        missing = not image_refs or any(entry is None for entry in observed)
        state = ("CVE_DETECTED" if vulnerable else
                 "SCAN_ERROR" if bad_scan else
                 "PENDING_EVIDENCE" if missing else
                 "CLEAN_IN_AVAILABLE_EVIDENCE")
        cves = sorted({cve for data in observed if data
                       for cve in data.get("cves", [])})
        rows.append({
            "app": app.folder, "status": state, "images": len(image_refs),
            "missing_images": [i for i in image_refs if i not in evidence],
            "errored_images": [i for i in image_refs
                              if evidence.get(i, {}).get("status") == "SCANNER_ERROR"],
            "vulnerable_images": [i for i in image_refs
                                 if evidence.get(i, {}).get("status") == "VULNERABLE"],
            # Totals include per-architecture observations; not unique CVEs.
            "critical_observations": sum(x["critical"] for x in observed if x),
            "high_observations": sum(x["high"] for x in observed if x),
            "cves": cves,
            "final_release_approved": False,  # separate release_catalog gate
        })
    return {
        "source_sha": source_sha, "images_expected": len(set(
            service["image"] for item in items for service in item.source["services"].values()
            if isinstance(service, dict) and "image" in service)),
        "images_with_evidence": len(evidence), "shard_warnings": warnings,
        "all_shards_valid": not warnings,
        "app_status_counts": dict(Counter(row["status"] for row in rows)),
        "apps": rows,
        "policy": ("Read-only diagnostic: clean observations are not proof of release "
                   "approval; only release_catalog with complete approved digest "
                   "evidence and Compose safety checks can authorize publication."),
    }


def markdown(report: dict) -> str:
    lines = ["# MrStore — CVE por aplicação (A–Z)", "",
             f"Fonte: commit \`{report['source_sha'] or 'não indicado'}\`",
             f"Imagens com evidência: **{report['images_with_evidence']}/{report['images_expected']}**",
             f"Shards válidos: {'8/8' if report['all_shards_valid'] else 'menos de 8/8'}",
             "", "**Apenas diagnóstico; nenhuma app é aqui declarada segura para publicação.**",
             "O total HIGH/CRITICAL soma observações por arquitetura e pode repetir CVEs.",
             "", "## Aplicações", "",
             "| App | Estado | Imagens pendentes / erro | HIGH | CRITICAL | IDs CVE observados |",
             "|---|---|---:|---:|---:|---|"]
    for row in report["apps"]:
        pending = len(row["missing_images"]) + len(row["errored_images"])
        cves = ", ".join(row["cves"][:8]) + (
            f" (+{len(row['cves'])-8})" if len(row["cves"]) > 8 else "")
        lines.append(
            f"| \`{row['app']}\` | {row['status']} | {pending} | "
            f"{row['high_observations']} | {row['critical_observations']} | {cves or '—'} |"
        )
    lines.extend(["", "## Pendências da auditoria", ""])
    if report["shard_warnings"]:
        lines.extend("- " + message for message in report["shard_warnings"])
    else:
        lines.append("- Os oito relatórios estão presentes e estruturalmente válidos.")
    lines.extend(["", "## Aplicações sem validação completa ou com CVEs", ""])
    for row in report["apps"]:
        if row["status"] != "CLEAN_IN_AVAILABLE_EVIDENCE":
            lines.append(f"- \`{row['app']}\` — {row['status']}")
    lines.append("")
    return "\n".join(lines)


def output_report(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "cve-apps.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "cve-apps.md").write_text(markdown(report), encoding="utf-8")
    with (output / "cve-apps.csv").open("w", encoding="utf-8-sig", newline="") as file:
        fields = ("app", "status", "images", "missing_images",
                  "errored_images", "vulnerable_images",
                  "high_observations", "critical_observations", "cves",
                  "final_release_approved")
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in report["apps"]:
            writer.writerow({key: "; ".join(row[key]) if isinstance(row.get(key), list)
                             else row.get(key) for key in fields})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("out/cve-apps"))
    parser.add_argument("--source-sha", default="")
    args = parser.parse_args()
    entries = apps(args.root)
    usage = image_usage(entries)
    image_arches = image_platforms(entries)
    evidence, warnings = load_evidence(args.evidence, usage, image_arches)
    report = make_report(entries, evidence, warnings, args.source_sha)
    output_report(report, args.output)
    if "GITHUB_STEP_SUMMARY" in __import__("os").environ:
        with open(__import__("os").environ["GITHUB_STEP_SUMMARY"],
                  "a", encoding="utf-8") as handle:
            handle.write(markdown(report))
    print(f"{len(report['apps'])} apps, {len(evidence)}/{len(usage)} images; "
          f"{len(warnings)} incomplete shards")
    return 0  # A generated diagnostic is not a release approval.


if __name__ == "__main__":
    sys.exit(main())
