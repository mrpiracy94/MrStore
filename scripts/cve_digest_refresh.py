#!/usr/bin/env python3
"""Compare current SHA-pinned image to newest digest of the SAME vendor tag.

Read-only: never upgrades hosts, mutates Apps/, or changes approved digests.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from catalog import ROOT, apps
from upstream_image_audit import trivy_counts
from updates import digest as resolve

PINNED = re.compile(r"^(.+)@(sha256:[0-9a-f]{64})$")
ARCHES = {"amd64", "arm64"}


def get_item(root: Path, app_name: str) -> dict:
    items = {item.folder: item for item in apps(root)}
    app = items.get(app_name)
    if app is None:
        raise ValueError("Unknown app " + app_name)
    name = app.metadata.get("main")
    services = app.source.get("services")
    if not isinstance(services, dict) or name not in services:
        raise ValueError("Invalid main service for " + app_name)
    spec = services[name]
    if not isinstance(spec, dict) or not isinstance(spec.get("image"), str):
        raise ValueError("Missing main service image for " + app_name)
    current = spec["image"]
    match = PINNED.fullmatch(current)
    if not match:
        raise ValueError("Current image is not pinned " + app_name)
    arches = app.metadata.get("architectures")
    if not isinstance(arches, list) or not arches or not set(arches) <= ARCHES:
        raise ValueError("No known architectures for " + app_name)
    baseline = json.loads((root / "data/image-digests.json").read_text(encoding="utf-8"))
    approved = baseline.get("images", {})
    if approved.get(current, approved.get(match.group(1))) != match.group(2):
        raise ValueError("Pinned source digest differs from baseline: " + app_name)
    return {
        "app": app_name, "service": name, "current_image": current,
        "tag": match.group(1), "current_digest": match.group(2),
        "architectures": sorted(set(arches)),
        "compose_path": str(app.path.relative_to(root)),
    }


def evaluate(item: dict, resolver=resolve, scanner=trivy_counts) -> dict:
    output = {
        "app": item["app"], "service": item["service"],
        "compose_path": item["compose_path"], "tag": item["tag"],
        "current_image": item["current_image"],
        "platforms": {}, "checked_at": datetime.now(timezone.utc).isoformat(),
        "automatic_update_allowed": False, "result": "inconclusive",
    }
    try:
        target, error = resolver(item["tag"])
        if error or not target:
            raise ValueError("Registry lookup failed: " + str(error or "empty digest"))
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", target):
            raise ValueError("Registry returned malformed digest")
        output["candidate_image"] = item["tag"] + "@" + target
        if target == item["current_digest"]:
            output["result"] = "unchanged"
            return output
        any_improvement = False
        all_nonregressing = True
        for arch in item["architectures"]:
            old = scanner(item["current_image"], arch)
            new = scanner(output["candidate_image"], arch)
            valid = all(
                type(counts.get(key)) is int and counts[key] >= 0
                for counts in (old, new) for key in ("high", "critical")
            )
            if not valid:
                raise ValueError("Invalid scanner counts for " + arch)
            improved = (new["critical"] <= old["critical"] and
                        new["high"] <= old["high"] and
                        (new["critical"] < old["critical"] or new["high"] < old["high"]))
            any_improvement = any_improvement or improved
            all_nonregressing = all_nonregressing and (new["critical"] <= old["critical"] and new["high"] <= old["high"])
            output["platforms"][arch] = {
                "current": old, "candidate": new, "lower_cves": improved}
        output["result"] = ("lower_observed_cves" if all_nonregressing and any_improvement
                            else "not_better_on_all_architectures")
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        output["result"] = "inconclusive"
        output["error"] = str(exc)[:1000]
    return output


def render(result: dict) -> str:
    lines = ["# MrStore - redução de CVEs após atualização da mesma imagem", "",
             "- App: " + result["app"],
             "- Imagem atual: " + result["current_image"],
             "- Candidata: " + result.get("candidate_image", "não resolvida"),
             "- Estado: **" + result["result"] + "**", "",
             "| Arquitetura | Atual (C/H) | Candidata (C/H) | Melhoria? |",
             "|---|---|---|---|"]
    for arch, row in result["platforms"].items():
        c, n = row["current"], row["candidate"]
        lines.append(f"| {arch} | {c['critical']}/{c['high']} | "
                     f"{n['critical']}/{n['high']} | {row['lower_cves']} |")
    lines.extend(["", "Menos ocorrências não prova menor risco global. "
                  "Nenhum Compose nem contentor foi alterado."])
    if result.get("error"):
        lines += ["", "Erro: " + result["error"]]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--app", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "out/digest-remediation")
    args = parser.parse_args(argv)
    try:
        item = get_item(args.root, args.app)
    except (OSError, ValueError, KeyError) as exc:
        print("CVE remediation BLOCKED:", exc, file=sys.stderr)
        return 2
    result = evaluate(item)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / (args.app + ".json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = render(result)
    (args.output / (args.app + ".md")).write_text(markdown, encoding="utf-8")
    print(markdown)
    return 2 if result["result"] == "inconclusive" else 0


if __name__ == "__main__":
    raise SystemExit(main())
