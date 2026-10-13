#!/usr/bin/env python3
"""Compare project-published Docker images with current MrStore images.

Read-only: does not edit manifests, upgrade containers or approve deployment.
Registry namespace does not alone prove upstream ownership or security.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from catalog import ROOT, apps, image_usage

SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
PINNED = re.compile(r"@sha256:[0-9a-f]{64}$")
REF = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*:[a-zA-Z0-9._-]+$")
ARCHES = {"amd64", "arm64"}

def publisher_class(image):
    if image.startswith("lscr.io/linuxserver/"):
        return "third_party_linuxserver"
    if image.startswith("ghcr.io/mrpiracy94/"):
        return "mrstore_rebuild"
    return "publisher_not_verified"

def candidates(root, catalog):
    path = root / "data/upstream-candidates.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Empty/invalid candidate inventory")
    lookup = {app.folder: app for app in catalog}
    seen, output = set(), []
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("Invalid candidate entry")
        name, service = row.get("app"), row.get("service")
        if not isinstance(name, str) or not isinstance(service, str):
            raise ValueError("Missing candidate app/service")
        if (name, service) in seen:
            raise ValueError("Duplicate candidate")
        seen.add((name, service))
        app = lookup.get(name)
        if app is None:
            raise ValueError("Unknown app " + name)
        spec = (app.source.get("services") or {}).get(service)
        if not isinstance(spec, dict) or not isinstance(spec.get("image"), str):
            raise ValueError("Unknown service " + name + "/" + service)
        current = spec["image"]
        candidate = row.get("candidate_image")
        source = row.get("source_url")
        if not PINNED.search(current):
            raise ValueError("Original is not digest-pinned: " + name)
        if not isinstance(candidate, str) or not REF.fullmatch(candidate):
            raise ValueError("Untrusted candidate image: " + name)
        if current.split("@", 1)[0] == candidate:
            raise ValueError("Candidate equals original: " + name)
        if not isinstance(source, str) or not source.startswith((
            "https://github.com/", "https://www.home-assistant.io/",
            "https://jellyfin.org/", "https://hub.docker.com/")):
            raise ValueError("Missing project source: " + name)
        if row.get("migration_status") != "needs_runtime_validation":
            raise ValueError("Migration is not yet validated: " + name)
        if not isinstance(row.get("migration_risk"), str) or not row["migration_risk"].strip():
            raise ValueError("Missing migration risk: " + name)
        arches = app.metadata.get("architectures")
        if not isinstance(arches, list) or not arches or not set(arches) <= ARCHES:
            raise ValueError("Unknown candidate architectures: " + name)
        output.append({**row, "current_image": current, "architectures": sorted(set(arches))})
    return sorted(output, key=lambda x: x["app"])

def audit(root=ROOT):
    items = apps(root)
    usage = image_usage(items)
    return {
        "apps": len(items), "unique_images": len(usage),
        "publisher_classes": dict(sorted(Counter(publisher_class(ref) for ref in usage).items())),
        "candidates": candidates(root, items),
        "limitations": "Publisher namespace is not security evidence; no deploys or migrations.",
    }

def command(args, timeout=550):
    proc = subprocess.run(args, capture_output=True, text=True,
                          check=False, timeout=timeout)
    if proc.returncode:
        raise RuntimeError(str(args[0]) + ": " + (proc.stderr or proc.stdout)[-700:])
    return proc.stdout.strip()

def resolve_digest(image):
    digest = command(["crane", "digest", image], timeout=180)
    if not SHA.fullmatch(digest):
        raise ValueError("Candidate registry digest invalid")
    return image + "@" + digest

def trivy_counts(image, arch):
    if arch not in ARCHES:
        raise ValueError("Unknown architecture")
    doc = json.loads(command([
        "trivy", "image", "--quiet", "--scanners", "vuln",
        "--severity", "HIGH,CRITICAL", "--image-src", "remote",
        "--platform", "linux/" + arch, "--parallel", "2",
        "--format", "json", "--timeout", "8m", image]))
    results = doc.get("Results") if isinstance(doc, dict) else None
    if not isinstance(results, list) or not results:
        raise ValueError("Trivy returned no targets")
    counts = {"CRITICAL": 0, "HIGH": 0}
    seen = set()
    for target in results:
        if not isinstance(target, dict) or not isinstance(target.get("Target"), str) or not target["Target"]:
            raise ValueError("Malformed scan target")
        findings = target.get("Vulnerabilities")
        if findings is None:
            findings = []
        if not isinstance(findings, list):
            raise ValueError("Malformed CVE findings")
        for item in findings:
            if not isinstance(item, dict):
                raise ValueError("Malformed vulnerability entry")
            severity = item.get("Severity")
            if severity not in counts:
                continue
            key = (target["Target"], item.get("VulnerabilityID"), item.get("PkgName"), item.get("InstalledVersion"))
            if key not in seen:
                seen.add(key)
                counts[severity] += 1
    return {"critical": counts["CRITICAL"], "high": counts["HIGH"]}

def compare(item):
    result = {"app": item["app"], "current_image": item["current_image"],
              "candidate_image": item["candidate_image"], "architectures": {},
              "checked_at": datetime.now(timezone.utc).isoformat(),
              "migration_status": "needs_runtime_validation",
              "automatic_migration_allowed": False}
    try:
        official_pinned = resolve_digest(item["candidate_image"])
        result["candidate_pinned"] = official_pinned
        any_improvement = False
        all_nonregressing = True
        for arch in item["architectures"]:
            current = trivy_counts(item["current_image"], arch)
            candidate = trivy_counts(official_pinned, arch)
            for counts in (current, candidate):
                if not isinstance(counts, dict) or any(
                    type(counts.get(severity)) is not int or counts[severity] < 0
                    for severity in ("critical", "high")
                ):
                    raise ValueError("Invalid Trivy CVE counts for " + arch)
            lower = (candidate["critical"] <= current["critical"] and
                     candidate["high"] <= current["high"] and
                     (candidate["critical"] < current["critical"] or
                      candidate["high"] < current["high"]))
            any_improvement = any_improvement or lower
            all_nonregressing = all_nonregressing and (candidate["critical"] <= current["critical"] and candidate["high"] <= current["high"])
            result["architectures"][arch] = {
                "current": current, "candidate": candidate, "lower_cves": lower}
        result["classification"] = (
            "candidate_lower_observed_cves"
            if all_nonregressing and any_improvement
            else "not_better_on_all_architectures")
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        result["classification"] = "inconclusive"
        result["error"] = str(exc)[:1000]
    return result

def markdown(report, comparisons):
    lines = ["# MrStore — auditoria de imagem de origem", "",
             "Apps: " + str(report["apps"]),
             "Imagens unicas: " + str(report["unique_images"]), "",
             "## Classificacao de proveniencia", ""]
    for key, count in report["publisher_classes"].items():
        lines.append("- " + key + ": " + str(count))
    lines += ["", "Origem nao significa certificacao CVE.",
              "Apenas substituicoes testadas em ambiente isolado podem ser propostas.",
              "", "## Comparacao atual versus candidata", ""]
    for row in comparisons:
        lines.append("- " + row["app"] + ": " + row["classification"])
        for arch, scans in row["architectures"].items():
            lines.append("  - " + arch + ": atual " + str(scans["current"]) +
                         " -> candidata " + str(scans["candidate"]))
        if row.get("error"):
            lines.append("  - erro: " + row["error"])
    return "\n".join(lines) + "\n"

def main(argv=None):
    cli = argparse.ArgumentParser()
    cli.add_argument("--root", type=Path, default=ROOT)
    cli.add_argument("--output", type=Path, default=ROOT / "out/upstream-images")
    cli.add_argument("--compare", action="store_true")
    cli.add_argument("--app")
    args = cli.parse_args(argv)
    try:
        report = audit(args.root)
    except (OSError, ValueError, KeyError) as exc:
        print("BLOCKED:", exc, file=sys.stderr)
        return 2
    if args.app and not args.compare:
        cli.error("--app requires --compare")
    subset = [x for x in report["candidates"] if not args.app or x["app"] == args.app]
    if args.app and not subset:
        cli.error("Unknown app " + args.app)
    comparisons = [compare(x) for x in subset] if args.compare else []
    args.output.mkdir(parents=True, exist_ok=True)
    suffix = "-" + args.app if args.app else ""
    (args.output / ("upstream-audit" + suffix + ".json")).write_text(
        json.dumps({"inventory": report, "comparisons": comparisons},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    note = markdown(report, comparisons)
    (args.output / ("upstream-audit" + suffix + ".md")).write_text(note, encoding="utf-8")
    print(note)
    return 2 if any(x["classification"] == "inconclusive" for x in comparisons) else 0

if __name__ == "__main__":
    sys.exit(main())
