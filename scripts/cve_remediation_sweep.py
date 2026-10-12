#!/usr/bin/env python3
"""Read-only eight-shard security upgrade checker for all MrStore images."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from catalog import ROOT, apps, image_usage
from cves import scan, shard_images
from cve_digest_refresh import evaluate
from release_scan import image_platforms
from updates import monitor


def count_cves(image: str, arch: str) -> dict:
    """Reuse the production Trivy scanner's registry retry and error handling."""
    vulns, error = scan(image, platform=arch)
    if error:
        raise RuntimeError(error)
    return {
        "critical": sum(v["severity"] == "CRITICAL" for v in vulns),
        "high": sum(v["severity"] == "HIGH" for v in vulns),
    }


def inspect(root: Path, shard: int, shards: int = 8, resolver=None,
            scanner=count_cves, workers: int = 2) -> dict:
    items = apps(root)
    usage = image_usage(items)
    chosen = shard_images(usage, shard, shards)
    subset = {ref: usage[ref] for ref in chosen}
    approved = json.loads((root / "data/image-digests.json").read_text(encoding="utf-8"))
    if resolver is None:
        _, registry = monitor(subset, approved, workers=workers)
    else:
        _, registry = monitor(subset, approved, resolver=resolver, workers=workers)
    platforms = image_platforms(items)
    comparisons = []
    for change in registry["changed"]:
        tag = change["image"]
        source = change["source_image"]
        if source not in subset or source not in platforms:
            raise ValueError("Candidate is not in approved source shard: " + source)
        app_name, service = change["apps"][0].split("/", 1)
        entry = {
            "app": app_name, "service": service,
            "compose_path": "Apps/" + app_name + "/docker-compose.yml",
            "current_image": source, "tag": tag,
            "current_digest": change["old"],
            "architectures": platforms[source],
        }
        def same_vendor(resolved_tag, *, expected_tag=tag, candidate=change["new"]):
            if resolved_tag != expected_tag:
                raise ValueError("Attempted cross-vendor substitution")
            return candidate, None
        outcome = evaluate(entry, resolver=same_vendor, scanner=scanner)
        outcome["all_app_services"] = change["apps"]
        comparisons.append(outcome)
    status_counts = Counter(row["result"] for row in comparisons)
    incomplete = bool(registry["failed"] or status_counts.get("inconclusive"))
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "source_app_count": len(items), "all_images": len(usage),
        "shard": shard, "shards": shards,
        "checked_images": len(chosen),
        "registry_resolved": registry["resolved"],
        "unchanged_images": registry["resolved"] - len(registry["changed"])
                            - len(registry["first_seen"]),
        "changed_images": len(registry["changed"]),
        "first_seen": registry["first_seen"],
        "registry_errors": registry["failed"],
        "comparison_counts": dict(sorted(status_counts.items())),
        "comparisons": comparisons,
        "complete": not incomplete,
        "automatic_migration_allowed": False,
    }


def markdown(report: dict) -> str:
    lines = ["# MrStore - CVE remediation opportunities", "",
             f"Shard: {report['shard']+1}/{report['shards']}",
             f"Catalog: {report['source_app_count']} apps / {report['all_images']} images",
             f"Images checked: {report['checked_images']}",
             f"Registry resolved: {report['registry_resolved']}",
             f"Digest unchanged: {report['unchanged_images']}",
             f"Digest changed: {report['changed_images']}",
             f"Scan complete: {report['complete']}", "",
             "| App/service | Result | CVE counts CRITICAL/HIGH |",
             "|---|---|---|"]
    for row in report["comparisons"]:
        delta = "; ".join(
            f"{arch}: {value['current']['critical']}/{value['current']['high']} -> "
            f"{value['candidate']['critical']}/{value['candidate']['high']}"
            for arch, value in row["platforms"].items()
        )
        if not delta:
            delta = row.get("error", "no scan")
        lines.append(f"| {row['app']}/{row['service']} | {row['result']} | {delta} |")
    for error in report["registry_errors"]:
        lines.append(f"- Registry inconclusive: {error['image']}: {error['error']}")
    lines.extend(["", "No image was installed, upgraded or approved.",
                  "A lower CVE count requires release notes, compatibility, "
                  "backup and rollback tests before a separate migration PR.",
                  "Registry or Trivy errors never mean zero vulnerabilities.", ""])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--expect-apps", type=int, default=254)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "out/remediation")
    args = parser.parse_args(argv)
    try:
        report = inspect(args.root, args.shard, args.shards, workers=args.workers)
        if args.expect_apps and report["source_app_count"] != args.expect_apps:
            raise ValueError("Catalog app count changed unexpectedly")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("REMEDIATION SWEEP BLOCKED:", exc, file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    basename = f"remediation-shard-{args.shard}"
    (args.output_dir / (basename + ".json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = markdown(report)
    (args.output_dir / (basename + ".md")).write_text(summary, encoding="utf-8")
    print(summary, flush=True)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
