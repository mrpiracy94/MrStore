"""Offline Docker Compose V2 parser audit of MrStore app definitions.

Never run/pull/build containers: only call docker compose config --quiet.
This tests Compose syntax and service relationships, NOT ZimaOS runtime.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess

from catalog import ROOT


def check_manifest(path: Path, root: Path, timeout: int = 35, runner=subprocess.run) -> dict:
    command = [
        "docker", "compose", "--ansi", "never",
        "-f", str(path.resolve()), "config", "--quiet", "--no-interpolate",
    ]
    try:
        output = runner(
            command, cwd=str(root.resolve()), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"app": path.parent.name, "ok": False, "reason": "compose parser timed out"}
    except OSError:
        return {"app": path.parent.name, "ok": False, "reason": "compose parser unavailable"}
    if output.returncode:
        reason = (output.stderr or output.stdout or "compose parser returned a nonzero code").strip()
        reason = " ".join(reason.splitlines())[:450]
        return {"app": path.parent.name, "ok": False, "reason": reason}
    return {"app": path.parent.name, "ok": True, "reason": ""}


def scan(root: Path = ROOT, workers: int = 6, runner=subprocess.run) -> dict:
    manifests = sorted((root / "Apps").glob("*/docker-compose.yml"))
    if not manifests:
        raise ValueError("No app manifests to validate")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda path: check_manifest(path, root, runner=runner), manifests))
    return {
        "tool": "docker compose config --quiet --no-interpolate",
        "scope": "static_parser_no_containers_started",
        "runtime_verified": False,
        "total": len(results),
        "passed": sum(x["ok"] for x in results),
        "failed": sum(not x["ok"] for x in results),
        "results": results,
    }


def to_markdown(data: dict) -> str:
    lines = [
        "# MrStore — Docker Compose parser audit", "",
        "**Offline parse only. No Docker images pulled, built, or started.**",
        f"Checked: {data['total']} | Pass: {data['passed']} | Fail: {data['failed']}",
        "",
    ]
    failures = [r for r in data["results"] if not r["ok"]]
    if failures:
        lines += ["## Parser failures", "", "| App | Docker Compose error |", "| --- | --- |"]
        for result in failures:
            msg = result["reason"].replace("|", "/")
            lines.append(f"| {result['app']} | {msg} |")
    else:
        lines.append("All app manifests parsed successfully. This is NOT ZimaOS runtime proof.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, choices=range(1, 13), default=6)
    parser.add_argument("--json", type=Path, default=ROOT / "out/compose-preflight.json")
    parser.add_argument("--md", type=Path, default=ROOT / "out/compose-preflight.md")
    args = parser.parse_args()
    if not shutil.which("docker"):
        raise SystemExit("Docker Compose CLI unavailable; static audit was NOT completed")
    data = scan(args.root, args.workers)
    for path, content in (
        (args.json, json.dumps(data, indent=2, ensure_ascii=False) + "\n"),
        (args.md, to_markdown(data)),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Compose static audit: {data['passed']}/{data['total']} passed; "
          f"{data['failed']} failed; 0 runtime verified")
    return 1 if data["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
