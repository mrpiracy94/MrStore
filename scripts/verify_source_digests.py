#!/usr/bin/env python3
"""Fail closed for any mutable or unreviewed Docker image in MrStore Apps/.

Source manifests MUST reference SHA256 digests from the committed baseline.
A digest fixes bytes; it does NOT prove that images are CVE-free or usable
on every architecture. This tool neither pulls nor runs containers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def inspect(root: Path) -> dict:
    baseline = json.loads((root / "data/image-digests.json").read_text(encoding="utf-8"))
    mapping = baseline.get("images")
    if not isinstance(mapping, dict):
        raise ValueError("Missing image digest baseline")
    paths = sorted((root / "Apps").glob("*/docker-compose.yml"))
    if not paths:
        raise ValueError("No Compose manifests to check")
    problems = []
    refs = 0
    for path in paths:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        services = document.get("services") if isinstance(document, dict) else None
        if not isinstance(services, dict) or not services:
            problems.append(f"{path.parent.name}: missing services")
            continue
        for name, spec in services.items():
            if not isinstance(spec, dict) or not isinstance(spec.get("image"), str):
                problems.append(f"{path.parent.name}/{name}: missing string image")
                continue
            refs += 1
            image = spec["image"]
            if "@sha256:" not in image:
                problems.append(f"{path.parent.name}/{name}: mutable image reference")
                continue
            tag, supplied = image.rsplit("@", 1)
            expected = mapping.get(image, mapping.get(tag))
            if not DIGEST.fullmatch(supplied) or not DIGEST.fullmatch(str(expected)):
                problems.append(f"{path.parent.name}/{name}: digest missing or invalid in baseline")
            elif supplied != expected:
                problems.append(f"{path.parent.name}/{name}: image digest differs from approved baseline")
    return {"apps": len(paths), "service_images": refs, "problems": problems}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print("Image source policy BLOCKED:", exc, file=sys.stderr)
        return 2
    for reason in result["problems"]:
        print("BLOCK:", reason, file=sys.stderr)
    print(f"Source image gate: {result['apps']} apps, {result['service_images']} images, "
          f"{len(result['problems'])} violations")
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
