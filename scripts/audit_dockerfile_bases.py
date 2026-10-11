#!/usr/bin/env python3
"""Audit ALL first-party Dockerfile base images by digest and architecture.

This cannot certify built derivative images. Unresolved ARGs and scan failures
are never reported as clean. No containers are run.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
from catalog import ROOT
from cves import scan
from release_scan import resolve_digest

ARG = re.compile(r"(?im)^\s*ARG\s+([A-Za-z_][A-Za-z0-9_]*)(?:=([^\s#]+))?")
FROM = re.compile(r"(?im)^\s*FROM\s+(?:(?:--platform=\S+)\s+)?(\S+)(?:\s+AS\s+(\S+))?\s*$")
VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")


def references(text):
    values = {name: value for name, value in ARG.findall(text) if value}
    stages = set()
    result = []
    for match in FROM.finditer(text):
        base, alias = match.groups()
        def substitute(m):
            return values.get(m.group(1) or m.group(2), m.group(0))
        expanded = VAR.sub(substitute, base)
        if base not in stages and not base.isdigit():
            result.append(expanded)
        if alias:
            stages.add(alias)
    return result


def catalog_bases(root):
    paths = sorted((root / "security/images").glob("*/Dockerfile"))
    if not paths:
        raise ValueError("No Dockerfiles found")
    refs = defaultdict(set)
    for path in paths:
        for ref in references(path.read_text(encoding="utf-8")):
            refs[ref].add(path.relative_to(root).as_posix())
    return {key: sorted(value) for key, value in sorted(refs.items())}


def audit(root, shard, shards, resolver=resolve_digest, scanner=scan):
    if shards < 1 or not 0 <= shard < shards:
        raise ValueError("Invalid scan shard")
    source = catalog_bases(root)
    results = []
    for idx, (ref, files) in enumerate(source.items()):
        if idx % shards != shard:
            continue
        if "$" in ref:
            results.append({"image": ref, "dockerfiles": files, "pinned": None,
                            "status": "needs_build_arg", "scans": {},
                            "error": "Dockerfile ARG unresolved"})
            continue
        pinned, error = resolver(ref)
        scans = {}
        if pinned and not error:
            for arch in ("amd64", "arm64"):
                try:
                    hits, failure = scanner(pinned, platform=arch)
                except Exception as exc:
                    hits, failure = [], "Scanner failed: " + str(exc)
                scans[arch] = {"status": "error" if failure else "ok", "error": failure,
                               "high": sum(x.get("severity") == "HIGH" for x in hits),
                               "critical": sum(x.get("severity") == "CRITICAL" for x in hits),
                               "findings": hits}
        status = ("error" if error or not pinned or len(scans) != 2
                  or any(x["status"] == "error" for x in scans.values())
                  else "vulnerable" if any(x["high"] or x["critical"] for x in scans.values())
                  else "clean")
        results.append({"image": ref, "dockerfiles": files, "pinned": pinned,
                        "status": status, "scans": scans, "error": error})
    return {"scope": "all_first_party_dockerfile_bases", "shard": shard,
            "shards": shards, "total_base_refs": len(source),
            "results": results,
            "limitations": ["Unknown build ARGs are not clean",
                            "Base scans do not certify derived images"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shard", type=int, required=True)
    p.add_argument("--shards", type=int, default=4)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--out", type=Path, default=ROOT / "out")
    o = p.parse_args()
    try:
        data = audit(o.root, o.shard, o.shards)
        o.out.mkdir(parents=True, exist_ok=True)
        (o.out / f"dockerfile-base-scan-{o.shard}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("Base-image audit incomplete:", exc)
        return 2
    risks = [x for x in data["results"] if x["status"] != "clean"]
    print(f"Dockerfile bases shard {o.shard}: {len(data['results'])} checked; {len(risks)} unsafe/pending")
    for row in risks:
        print(f"REVIEW {row['image']}: {row['status']}")
    return 1 if risks else 0


if __name__ == "__main__":
    raise SystemExit(main())
