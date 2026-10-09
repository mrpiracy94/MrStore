"""Verify mandatory Compose variables fail closed before deployment.

No image is downloaded, built, or started. All supplied values are fake.
The ZimaOS installation form and runtime are NOT exercised by this test.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from catalog import ROOT, apps

REQUIRED_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*):\?[^}]+\}")


def required_by_app(root: Path = ROOT) -> dict[str, list[str]]:
    found = {}
    for app in apps(root):
        variables = set()
        for spec in app.source["services"].values():
            if not isinstance(spec, dict):
                continue
            env = spec.get("environment") or []
            entries = (env.values() if isinstance(env, dict) else env)
            for entry in entries:
                variables.update(REQUIRED_RE.findall(str(entry)))
        if variables:
            found[app.folder] = sorted(variables)
    return found


def check_one(path: Path, required: list[str], runner=subprocess.run) -> dict:
    # --env-file /dev/null makes this deterministic and ignores per-app .env files.
    # Do not use user credentials from CI or the machine; inject fake strings only.
    command = ["docker", "compose", "--ansi", "never", "--env-file", "/dev/null",
               "-f", str(path.resolve()), "config", "--quiet"]
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),
        "COMPOSE_DISABLE_ENV_FILE": "1",
    }
    for variable in required:
        env[variable] = "MRSTORE_SYNTHETIC_TEST_VALUE"
    failures = []
    attempts = 0

    def run_checked(test_env):
        return runner(command, env=test_env, capture_output=True, text=True, timeout=35)

    try:
        attempts += 1
        if run_checked(env).returncode != 0:
            failures.append("synthetic values did not pass Compose parsing")
        for variable in required:
            for test_kind, value in (("missing", None), ("empty", "")):
                modified = dict(env)
                if value is None:
                    modified.pop(variable, None)
                else:
                    modified[variable] = value
                attempts += 1
                result = run_checked(modified)
                # A failure with an unrelated cause cannot count as a successful
                # secret gate test; insist on Docker's required variable message.
                output = (result.stderr or "") + (result.stdout or "")
                if result.returncode == 0 or variable not in output:
                    failures.append(f"{variable}: {test_kind} did not fail as required")
    except (OSError, subprocess.TimeoutExpired) as exc:
        failures.append(f"Compose CLI unavailable or timeout: {type(exc).__name__}")
    return {"app": path.parent.name, "variables": required, "checks": attempts,
            "ok": not failures, "failures": failures}


def verify(root: Path = ROOT, runner=subprocess.run) -> dict:
    required = required_by_app(root)
    if not required:
        raise ValueError("No required variables found; refuse a vacuous pass")
    results = [
        check_one(root / "Apps" / name / "docker-compose.yml", variables, runner)
        for name, variables in sorted(required.items())
    ]
    return {
        "scope": "docker_compose_config_only_no_containers",
        "zimaos_runtime_verified": False,
        "applications": len(results),
        "unique_required_variables_per_app": sum(len(variables) for variables in required.values()),
        "checks": sum(item["checks"] for item in results),
        "passed": sum(item["ok"] for item in results),
        "failed": sum(not item["ok"] for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "out/required-secrets.json")
    args = parser.parse_args()
    if not shutil.which("docker"):
        raise SystemExit("Docker Compose unavailable; required-secret check NOT performed")
    report = verify(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Compose required-secrets: {report['passed']}/{report['applications']} apps passed, "
          f"{report['checks']} synthetic checks, {report['failed']} failed, "
          "zero ZimaOS runtime installations")
    for item in report["results"]:
        if not item["ok"]:
            print(item["app"] + ": " + "; ".join(item["failures"]))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
