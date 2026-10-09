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
import time
from catalog import ROOT, apps, image_usage
from cves import scan, shard_images, RETRYABLE, BACKOFF_SECONDS, MAX_ATTEMPTS

DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def resolve_digest(image: str, runner=subprocess.run, sleeper=time.sleep) -> tuple[str | None, str | None]:
    """Resolve a multiarch index digest; transient errors retry, never count as clean."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            proc = runner(["crane", "digest", image], capture_output=True,
                          text=True, timeout=90, check=False)
            digest = proc.stdout.strip()
            if proc.returncode == 0 and DIGEST.fullmatch(digest):
                # Never silently remap a pre-pinned image to another digest.
                if "@sha256:" in image:
                    supplied = "sha256:" + image.rsplit("@sha256:", 1)[-1]
                    if supplied != digest:
                        return None, "registry digest does not match pinned manifest"
                    return image, None
                return image + "@" + digest, None
            error = (proc.stderr or proc.stdout or "invalid registry digest").strip()[-400:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = str(exc)
        if attempt == MAX_ATTEMPTS or not RETRYABLE.search(error):
            return None, f"digest lookup failed ({attempt}/{MAX_ATTEMPTS}): {error}"
        seconds = BACKOFF_SECONDS[attempt - 1]
        print(f"Transient crane registry error on {image}; retry in {seconds}s", flush=True)
        sleeper(seconds)
    raise AssertionError("Unreachable digest retry state")


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
