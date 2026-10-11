#!/usr/bin/env python3
"""Fail closed if a GitHub workflow executes an unpinned third-party action.

Only 40-character full immutable commit SHAs are permitted for remote actions
and reusable workflows. Local paths under .github are allowed.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"(?m)^\s*(?:-\s*)?uses:\s*(\S+)")
PIN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?@[a-f0-9]{40}$")


def inspect_workflow(text: str, name: str) -> list[str]:
    issues = []
    for match in LINE.finditer(text):
        value = match.group(1).strip('"\'')
        if value.startswith("./"):
            if ".." in Path(value).parts:
                issues.append(f"{name}: unsafe local action path")
            continue
        if not PIN.fullmatch(value):
            issues.append(f"{name}: third-party action must use full commit SHA: {value}")
    return issues


def inspect_repo(root: Path = ROOT) -> tuple[int, list[str]]:
    folder = root / ".github/workflows"
    files = sorted(folder.glob("*.yml")) + sorted(folder.glob("*.yaml"))
    if not files:
        raise ValueError("No GitHub workflows to validate")
    problems = []
    for file in files:
        problems.extend(inspect_workflow(file.read_text(encoding="utf-8"),
                                         file.relative_to(root).as_posix()))
    return len(files), problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        count, failures = inspect_repo(args.root)
    except (OSError, ValueError) as exc:
        print("GitHub Action pinning verification failed:", exc)
        return 2
    for problem in failures:
        print("BLOCK:", problem)
    print(f"Inspected {count} GitHub workflows: {len(failures)} unpinned/invalid action references")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
