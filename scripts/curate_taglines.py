#!/usr/bin/env python3
"""Curated, concise Portuguese card subtitles for the ZimaOS v2 catalog.

Only the top-level x-casaos.tagline and manifest revision are altered, in
memory/in the CI workspace before build. This does not run Docker or mutate
installed applications. Developer/author credits remain untouched.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
TAGLINES = ROOT / "data/taglines-pt.json"
TAGLINE_BLOCK = re.compile(r"(?m)^  tagline:\n(?:    (?:en_US|pt_PT): [^\n]*\n)+")
MANIFEST_VERSION = re.compile(r'(?m)^  version: "(\d+)\.(\d+)\.(\d+)"[ \t]*$')
FORBIDDEN = re.compile(r"linuxserver(?:\.io)?|seedit4(?:\.me)?|quickbox|catalog", re.I)


def load_summaries() -> dict[str, str]:
    summaries = json.loads(TAGLINES.read_text(encoding="utf-8"))
    if not isinstance(summaries, dict):
        raise ValueError("data/taglines-pt.json must be a JSON object")
    for app, subtitle in summaries.items():
        if not isinstance(subtitle, str) or not subtitle.strip():
            raise ValueError(f"Empty/non-string subtitle for {app!r}")
        if len(subtitle) > 85 or FORBIDDEN.search(subtitle):
            raise ValueError(f"Subtitle is too long or mentions a source: {app}: {subtitle}")
    return summaries


def render_manifest(source: str, app: str, subtitle: str) -> str:
    old = TAGLINE_BLOCK.search(source)
    if not old or len(TAGLINE_BLOCK.findall(source)) != 1:
        raise ValueError(f"{app}: expected one top-level x-casaos tagline")
    q = json.dumps(subtitle, ensure_ascii=False)
    block = f"  tagline:\n    en_US: {q}\n    pt_PT: {q}\n"
    changed = source[:old.start()] + block + source[old.end():]
    matches = MANIFEST_VERSION.findall(changed)
    if len(matches) != 1:
        raise ValueError(f"{app}: expected one quoted x-casaos version")
    major, minor, patch = map(int, matches[0])
    new_version = f'  version: "{major}.{minor}.{patch + 1}"'
    changed = MANIFEST_VERSION.sub(new_version, changed, count=1)
    before = yaml.safe_load(source)
    after = yaml.safe_load(changed)
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError(f"{app}: invalid Compose YAML")
    # Only a metadata card subtitle + locale and a revision may change.
    before_meta = before.pop("x-casaos")
    after_meta = after.pop("x-casaos")
    if before != after:
        raise ValueError(f"{app}: services/configuration changed unexpectedly")
    for key in ("tagline", "version"):
        before_meta.pop(key, None)
        after_meta.pop(key, None)
    if before_meta != after_meta:
        raise ValueError(f"{app}: unrelated app metadata changed")
    return changed


def prepare(*, check_only: bool) -> int:
    summaries = load_summaries()
    files = sorted((ROOT / "Apps").glob("*/docker-compose.yml"))
    actual = {p.parent.name for p in files}
    expected = set(summaries)
    if actual != expected or len(files) != 254:
        raise ValueError(
            f"Catalog/subtitle mismatch: {len(files)} Compose, "
            f"missing={sorted(actual - expected)}, extra={sorted(expected - actual)}"
        )
    updated = []
    for path in files:
        current = path.read_text(encoding="utf-8")
        result = render_manifest(current, path.parent.name, summaries[path.parent.name])
        updated.append((path, result))
    if not check_only:
        for path, result in updated:
            path.write_text(result, encoding="utf-8")
    print(f"Validated {len(updated)} curated Portuguese card subtitles; "
          f"{'no files written' if check_only else 'build workspace updated'}")
    return len(updated)


def verify_published(index_path: Path) -> int:
    summaries = load_summaries()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = index.get("apps")
    if not isinstance(entries, list):
        raise ValueError("ZimaOS index.json is missing an apps list")
    if len(entries) != 254:
        raise ValueError(f"Expected 254 published apps, found {len(entries)}")
    seen = set()
    for item in entries:
        app_id = item["id"]
        prefix = "io.github.mrpiracy94."
        if not app_id.startswith(prefix):
            raise ValueError(f"Unexpected app ID: {app_id}")
        app = app_id[len(prefix):]
        if app not in summaries or app in seen:
            raise ValueError(f"Unknown or duplicate published app {app}")
        seen.add(app)
        if item.get("tagline") != summaries[app]:
            raise ValueError(f"{app}: published subtitle differs from approved summary")
    if seen != set(summaries):
        raise ValueError(f"Missing published summaries: {sorted(set(summaries) - seen)}")
    print(f"Verified all {len(seen)} published ZimaOS card subtitles")
    return len(seen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without changing files")
    parser.add_argument("--verify-dist", type=Path, help="check published index.json subtitles")
    args = parser.parse_args()
    if args.verify_dist:
        verify_published(args.verify_dist)
    else:
        prepare(check_only=args.check)


if __name__ == "__main__":
    main()
