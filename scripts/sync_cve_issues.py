"""Keep a single issue per CVE shard without hiding vulnerabilities or scan errors.

This script is run with GH_TOKEN by the CVE workflow. Its only side effects are
GitHub issue updates; image manifests and the installed systems are untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


def sync(report_path: Path, summary_path: Path, runner=subprocess.run) -> dict:
    report_path = Path(report_path)
    summary_path = Path(summary_path)
    if not report_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("CVE report or summary missing; cannot synchronise issues")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    shard = report["shard"]
    if type(shard) is not int or not 0 <= shard < 8:
        raise ValueError("Invalid CVE shard")
    for key in ("critical", "high", "failures"):
        if type(report.get(key)) is not int or report[key] < 0:
            raise ValueError("Invalid CVE report count: " + key)

    title = f"MrStore CVE HIGH/CRITICAL — shard {shard}"
    old_title = f"MrStore CVE CRITICAL — shard {shard}"
    proc = runner(
        ["gh", "issue", "list", "--state", "all", "--limit", "200",
         "--json", "title,number,state"],
        capture_output=True, text=True, check=True,
    )
    entries = json.loads(proc.stdout)
    matches = sorted(
        (item for item in entries if item["title"] in (title, old_title)),
        key=lambda item: item["number"],
    )
    opened = [item for item in matches if item["state"].upper() == "OPEN"]
    current = (opened or matches or [None])[0]
    duplicates = [item for item in matches if item is not current]

    findings = report["critical"] or report["high"]
    failures = report["failures"]
    if findings:
        if current is None:
            runner(["gh", "issue", "create", "--title", title,
                    "--body-file", str(summary_path)], check=True)
            return {"action": "created", "duplicates_closed": 0}
        number = str(current["number"])
        if current["state"].upper() != "OPEN":
            runner(["gh", "issue", "reopen", number], check=True)
        runner(["gh", "issue", "edit", number, "--title", title,
                "--body-file", str(summary_path)], check=True)
        action = "updated"
    elif failures:
        # Scanner/network failures are never evidence that vulnerabilities cleared.
        return {"action": "scan_incomplete", "duplicates_closed": 0}
    else:
        action = "clean"
        if current and current["state"].upper() == "OPEN":
            number = str(current["number"])
            runner(["gh", "issue", "comment", number, "--body",
                    "Nova análise completa: sem CVEs HIGH/CRITICAL e sem falhas. "
                    "Relatório disponível nos artefactos do workflow."], check=True)
            runner(["gh", "issue", "close", number], check=True)
            action = "closed"

    # Consolidate only after updating the canonical issue successfully.
    # Leave each duplicate's historical evidence readable in its own issue.
    closed = 0
    for item in duplicates:
        if item["state"].upper() == "OPEN":
            number = str(item["number"])
            runner(["gh", "issue", "comment", number, "--body",
                    f"Relatório duplicado deste shard; acompanhamento em #{current['number']}. "
                    "Os resultados históricos deste issue permanecem disponíveis."], check=True)
            runner(["gh", "issue", "close", number], check=True)
            closed += 1
    return {"action": action, "duplicates_closed": closed}


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=Path, default=Path("out/cves.json"))
    p.add_argument("--summary", type=Path, default=Path("out/cves.md"))
    args = p.parse_args()
    print(sync(args.report, args.summary))


if __name__ == "__main__":
    main()
