"""Audit Docker image build recency without equating it to upstream release activity.

A registry image config's "created" timestamp is not a release date. An old
digest can be intentional; this report is a shortlist for human verification,
not a reason to quarantine/publish an image.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

from catalog import ROOT, apps, image_usage
from cves import shard_images

RETIRED_UPSTREAM = {
    "lscr.io/linuxserver/steamos:latest":
        "https://info.linuxserver.io/issues/2025-12-13-steamosdep/",
}
RETRY_MARKERS = ("429", "too many requests", "toomanyrequests", "timeout",
                 "timed out", "connection reset", "502", "503", "504")


def parse_created(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None  # Naive timestamps are ambiguous, never guess UTC.
    return dt.astimezone(timezone.utc)


def examine(image: str, ref_apps: list[str], now: datetime, runner=subprocess.run,
            sleeper=time.sleep) -> dict:
    """Read only the AMD64 image config; never pull/install/deploy the image."""
    # Most catalog entries support amd64; different platforms can have
    # different build dates. An AMD64 date does not certify ARM64 recency.
    cmd = ["crane", "config", "--platform", "linux/amd64", image]
    error = ""
    raw = None
    for attempt in range(2):
        try:
            p = runner(cmd, capture_output=True, text=True, timeout=90, check=False)
            if p.returncode == 0:
                raw = p.stdout
                break
            error = (p.stderr or p.stdout or f"crane exit {p.returncode}").strip()[-500:]
        except (subprocess.TimeoutExpired, OSError) as exc:
            error = str(exc)
        if attempt == 0 and any(k in error.lower() for k in RETRY_MARKERS):
            sleeper(5)
        else:
            break
    item = {"image": image, "apps": ref_apps,
            "reference": "immutable" if "@sha256:" in image else "tag",
            "platform": "linux/amd64",
            "build_created": None, "build_age_days": None,
            "status": "unknown", "error": None}
    if image in RETIRED_UPSTREAM:
        item["upstream_deprecation"] = RETIRED_UPSTREAM[image]
    if raw is None:
        item.update(status="error", error=error or "crane did not return image config")
        return item
    try:
        config = json.loads(raw)
    except ValueError:
        item.update(status="error", error="Registry returned invalid image config JSON")
        return item
    if not isinstance(config, dict):
        item.update(status="error", error="Registry image config was not an object")
        return item
    # An OCI label may help when created isn't set, but it can describe
    # source build time rather than the image build time. Keep provenance.
    created = parse_created(config.get("created"))
    source = "image_config"
    if created is None:
        labels = config.get("config") or {}
        labels = labels.get("Labels", {}) if isinstance(labels, dict) else {}
        if isinstance(labels, dict):
            created = parse_created(labels.get("org.opencontainers.image.created"))
            source = "oci_label"
    if created is None:
        return item
    delta_days = (now - created).total_seconds() / 86400
    item["build_created"] = created.isoformat()
    item["timestamp_source"] = source
    if delta_days < -1:
        item.update(status="unknown", error="Image build timestamp is in the future")
    else:
        age = max(0, int(delta_days))
        item["build_age_days"] = age
        item["status"] = ("build_365_plus" if age >= 365 else
                          "build_180_364" if age >= 180 else "build_under_180")
    return item


def analyze(usage: dict[str, list[str]], shard: int, shards: int,
            now: datetime | None = None, worker_count: int = 2,
            inspector=examine) -> dict:
    now = now or datetime.now(timezone.utc)
    chosen = shard_images(usage, shard, shards)
    with ThreadPoolExecutor(max_workers=max(1, min(worker_count, 4))) as pool:
        tasks = {pool.submit(inspector, image, usage[image], now): image
                 for image in chosen}
        results = []
        for future in as_completed(tasks):
            image = tasks[future]
            try:
                item = future.result()
            except Exception as exc:
                item = {"image": image, "apps": usage[image], "status": "error",
                        "error": str(exc), "build_created": None, "build_age_days": None}
            results.append(item)
    results.sort(key=lambda x: x["image"])
    from collections import Counter
    statuses = Counter(x["status"] for x in results)
    return {"checked_at": now.isoformat(), "shard": shard, "shards": shards,
            "images_checked": len(results), "total_images": len(usage),
            "counts": dict(sorted(statuses.items())), "results": results}


def summarize(report: dict) -> str:
    cs = report["counts"]
    lines = ["# MrStore — idade das imagens Docker", "",
             f"Grupo {report['shard']+1}/{report['shards']} — {report['images_checked']} referências",
             f"Build ≥365 dias: {cs.get('build_365_plus', 0)} | "
             f"180–364 dias: {cs.get('build_180_364', 0)} | "
             f"<180 dias: {cs.get('build_under_180', 0)} | "
             f"sem data: {cs.get('unknown', 0)} | "
             f"erros de registry: {cs.get('error', 0)}", "",
             "**Esta é a idade do build da imagem AMD64, não a última atualização do "
             "software nem um diagnóstico de abandono.** Digests fixos não recebem "
             "atualizações automaticamente. Analisar cada fornecedor antes de agir.", ""]
    old = sorted((x for x in report["results"]
                  if x["status"] in ("build_365_plus", "build_180_364")),
                 key=lambda x: -x["build_age_days"])
    for x in old:
        suffix = " (digest fixo)" if x["reference"] == "immutable" else ""
        lines.append(f"- {x['build_age_days']} dias — `{x['image']}`{suffix} "
                     f"({', '.join(x['apps'])})")
    for x in report["results"]:
        if x.get("upstream_deprecation"):
            lines.append(f"- **Fornecedor confirmou descontinuação:** "
                         f"`{x['image']}` — {x['upstream_deprecation']}")
        if x["status"] == "error":
            lines.append(f"- **Consulta inconclusiva:** `{x['image']}` — {x['error']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=ROOT / "out/image-freshness.json")
    parser.add_argument("--summary", type=Path, default=ROOT / "out/image-freshness.md")
    args = parser.parse_args()
    usage = image_usage(apps(ROOT))
    report = analyze(usage, args.shard, args.shards, worker_count=args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.summary.write_text(summarize(report))
    print(summarize(report))
    # This is a diagnostic, not a vulnerability scan or release gate.
    return 2 if report["counts"].get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
