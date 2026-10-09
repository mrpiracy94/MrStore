"""Scan immutable image digests on every declared platform for safe app releases.

Unlike the daily advisory scan, releases need proof for each manifest platform.
Scan failures and detected HIGH/CRITICAL findings are quarantined, never clean.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
from catalog import ROOT, apps, image_usage
from cves import scan, shard_images

DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def resolve_digest(image: str) -> tuple[str | None, str | None]:
    """Use the canonical multi-architecture index digest when one exists."""
    try:
        proc = subprocess.run(["crane", "digest", image], capture_output=True,
                              text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "digest lookup failed: " + str(exc)
    digest = proc.stdout.strip()
    if proc.returncode != 0 or not DIGEST.fullmatch(digest):
        return None, "digest lookup failed: " + (proc.stderr.strip()[:250] or "invalid result")
    # An already-pinned image must never be silently remapped.
    if "@sha256:" in image:
        supplied = "sha256:" + image.rsplit("@sha256:", 1)[-1]
        if supplied != digest:
            return None, "registry digest does not match pinned manifest"
        return image, None
    return image + "@" + digest, None


def image_platforms(items) -> dict[str, list[str]]:
    platforms: dict[str, set[str]] = {}
    for app in items:
        architectures = set(app.metadata.get("architectures") or [])
        if not architectures or not architectures <= {"amd64", "arm64"}:
            raise ValueError(f"{app.folder}: unsupported/missing architecture")
        for spec in (app.source.get("services") or {}).values():
            if isinstance(spec, dict) and spec.get("image"):
                platforms.setdefault(spec["image"], set()).update(architectures)
    return {image: sorted(values) for image, values in platforms.items()}


def audit_shard(items, shard: int, shards: int, resolver=resolve_digest, scanner=scan) -> dict:
    usage = image_usage(items)
    platforms = image_platforms(items)
    chosen = shard_images(usage, shard, shards)
    results = []
    for image in chosen:
        pinned, error = resolver(image)
        scans = {}
        if pinned and not error:
            for platform in platforms[image]:
                try:
                    findings, failure = scanner(pinned, platform=platform)
                except Exception as exc:
                    findings, failure = [], "scanner exception: " + str(exc)
                scans[platform] = {
                    "status": "error" if failure else "ok",
                    "error": failure,
                    "critical": sum(v.get("severity") == "CRITICAL" for v in findings),
                    "high": sum(v.get("severity") == "HIGH" for v in findings),
                }
        if error or not pinned or len(scans) != len(platforms[image]):
            status = "error"
        elif any(r["status"] == "error" for r in scans.values()):
            status = "error"
        elif any(r["critical"] or r["high"] for r in scans.values()):
            status = "vulnerable"
        else:
            status = "clean"
        results.append({
            "image": image, "pinned": pinned, "status": status,
            "error": error, "platforms": platforms[image], "scans": scans,
        })
        print(f"[{len(results)}/{len(chosen)}] {image}: {status}", flush=True)
    return {"shard": shard, "shards": shards, "images_total": len(usage),
            "images_checked": len(results), "results": results}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--shard", type=int, required=True)
    p.add_argument("--shards", type=int, default=8)
    p.add_argument("--output-dir", type=Path, default=ROOT / "out")
    o = p.parse_args()
    report = audit_shard(apps(), o.shard, o.shards)
    o.output_dir.mkdir(parents=True, exist_ok=True)
    dest = o.output_dir / f"release-cves-shard-{o.shard}.json"
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {status: sum(r["status"] == status for r in report["results"])
              for status in ("clean", "vulnerable", "error")}
    print(f"Shard {o.shard}: {counts}; report saved {dest}", flush=True)
    # Image vulnerabilities and registry failures are visible but do not block OTHER apps.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
