"""Audit every declared CPU architecture, independently, before catalog publication.

All Compose files remain data: containers are never executed on the runner.
A failed registry/Trivy lookup is recorded as unknown and never approved.
"""
import argparse
import json
from pathlib import Path

from catalog import ROOT, apps, image_usage
from cves import scan, shard_images


ARCHES = ("amd64", "arm64")


def declared_platforms(items):
    result = {}
    for app in items:
        arches = app.metadata.get("architectures")
        if not isinstance(arches, list) or not arches or any(
            arch not in ARCHES for arch in arches
        ):
            raise ValueError(f"{app.folder}: invalid declared architectures")
        for name, spec in app.source["services"].items():
            if not isinstance(spec, dict) or not isinstance(spec.get("image"), str):
                raise ValueError(f"{app.folder}/{name}: missing Docker image")
            result.setdefault(spec["image"], set()).update(arches)
    return {image: sorted(arches) for image, arches in result.items()}


def audit(usage, platforms, chosen, scanner=scan):
    results = []
    for image in chosen:
        checks = []
        for arch in platforms[image]:
            try:
                findings, error = scanner(image, platform=f"linux/{arch}")
            except Exception as exc:
                findings, error = [], str(exc)
            checks.append({
                "arch": arch,
                "status": "error" if error else "ok",
                "error": error,
                "findings": findings,
            })
        results.append({"image": image, "apps": usage[image], "checks": checks})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    items = apps(args.root)
    usage = image_usage(items)
    platforms = declared_platforms(items)
    if set(usage) != set(platforms):
        raise ValueError("Inconsistent image inventory")
    chosen = shard_images(usage, args.shard, args.shards)
    results = audit(usage, platforms, chosen)
    payload = {
        "schema": 1,
        "shard": args.shard,
        "shards": args.shards,
        "images_total": len(usage),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    high = sum(1 for r in results for c in r["checks"]
               for f in c["findings"] if f.get("severity") == "HIGH")
    critical = sum(1 for r in results for c in r["checks"]
                   for f in c["findings"] if f.get("severity") == "CRITICAL")
    errors = sum(c["status"] == "error" for r in results for c in r["checks"])
    print(f"Shard {args.shard}: images={len(results)}, HIGH={high}, "
          f"CRITICAL={critical}, incomplete={errors}")
    # Findings/errors are quarantined later; scanner/process failures still fail this job.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
