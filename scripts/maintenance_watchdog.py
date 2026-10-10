#!/usr/bin/env python3
"""Periodic, non-destructive MrStore review. Never merges, deploys or suppresses CVEs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TITLE = "[maintenance-watchdog] MrStore — revisão automática"
WORKFLOWS = {
    "cve-scan.yml": 60,
    "update-monitor.yml": 60,
    "catalog-uptime.yml": 30,
    "image-freshness.yml": 216,
    "discover-apps.yml": 960,
}
CHECKS = {
    "Manifestos e regras de segurança": ["scripts/validate.py"],
    "Resumos PT": ["scripts/curate_taglines.py", "--check"],
    "Testes de regressão": ["-m", "unittest", "discover", "-s", "tests", "-v"],
    "Docker Compose V2 (sem instalar)": ["scripts/compose_preflight.py"],
    "Sintaxe Python": ["-m", "compileall", "-q", "scripts", "tests"],
}


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def finding(kind: str, identifier: str, message: str, url: str = "") -> dict:
    return {"kind": kind, "id": identifier, "message": message, "url": url}


def evaluate_run(filename: str, runs: list[dict], now: datetime,
                 max_hours: int, repo: str,
                 workflow_created_at: str | None = None) -> tuple[str, dict | None]:
    """Alert on absent schedules only after the workflow's initial grace window.

    A workflow added today cannot already have a successful monthly or weekly
    scheduled execution. The grace window is bounded by its freshness SLA.
    Missing creation metadata is *not* accepted as proof of a healthy workflow.
    """
    link = f"https://github.com/{repo}/actions/workflows/{filename}"
    if not runs:
        if workflow_created_at:
            started = timestamp(workflow_created_at)
            age = (now - started).total_seconds() / 3600
            if 0 <= age <= max_hours:
                return (f"A aguardar primeira execução agendada (criado há {age:.0f} h)", None)
        return ("Sem execução agendada confirmada",
                finding("workflow", f"missing:{filename}",
                        f"**{filename}**: nenhuma execução agendada encontrada "
                        f"após período inicial de {max_hours} h ou sem data de criação verificável.",
                        link))
    run = max(runs, key=lambda item: item.get("created_at", ""))
    link = run.get("html_url") or link
    age = (now - timestamp(run["created_at"])).total_seconds() / 3600
    status = run.get("status")
    conclusion = run.get("conclusion")
    if status != "completed":
        if age > 6:
            return ("Execução pendente há mais de 6 h",
                    finding("workflow", f"stuck:{filename}",
                            f"**{filename}**: execução sem conclusão há {age:.0f} h.", link))
        return ("Em execução", None)
    if conclusion != "success":
        return (f"Última execução: {conclusion or 'inconclusiva'}",
                finding("workflow", f"failed:{filename}:{conclusion}",
                        f"**{filename}**: última execução agendada terminou com "
                        f"**{conclusion or 'resultado inconclusivo'}**; "
                        "verificar os logs, sem ignorar alertas de segurança.", link))
    if age > max_hours:
        return (f"Execução demasiado antiga ({age:.0f} h)",
                finding("workflow", f"stale:{filename}",
                        f"**{filename}**: última execução há {age:.0f} h "
                        f"(limite {max_hours} h).", link))
    return (f"OK, última execução há {age:.0f} h", None)


def stale_prs(prs: list[dict], now: datetime, repo: str,
              days: int = 14) -> list[dict]:
    problems = []
    for pr in prs:
        if not pr.get("updated_at"):
            problems.append(finding("pr", f"missing-date:{pr['number']}",
                                    f"PR #{pr['number']} sem data de atualização.",
                                    pr.get("html_url", "")))
            continue
        age = (now - timestamp(pr["updated_at"])).total_seconds() / 86400
        if age >= days:
            number = pr["number"]
            problems.append(finding("pr", f"stale-pr:{number}",
                                    f"PR #{number} sem atividade há {age:.0f} dias "
                                    f"({'draft' if pr.get('draft') else 'aberta'}); "
                                    "rever testes, bloqueios e próximo passo.",
                                    pr.get("html_url") or
                                    f"https://github.com/{repo}/pull/{number}"))
    return problems


def api(path: str, method: str = "GET", payload: dict | None = None):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN/GITHUB_TOKEN necessário para auditoria GitHub")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request("https://api.github.com" + path, data=data, method=method,
                      headers={"Accept": "application/vnd.github+json",
                               "Authorization": "Bearer " + token,
                               "X-GitHub-Api-Version": "2022-11-28",
                               "User-Agent": "mrstore-maintenance-watchdog",
                               "Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        body = response.read()
    return json.loads(body) if body else {}


def api_pages(path: str, key: str | None = None, limit: int = 10) -> list[dict]:
    items = []
    for page in range(1, limit + 1):
        sep = "&" if "?" in path else "?"
        data = api(f"{path}{sep}per_page=100&page={page}")
        batch = data.get(key, []) if key else data
        items.extend(batch)
        if len(batch) < 100:
            return items
    raise RuntimeError(f"GitHub pagination exceeded {limit} pages for {path}")


def local_review() -> tuple[list[dict], list[str], dict]:
    problems = []
    notes = []
    outcomes = {}
    for title, command in CHECKS.items():
        argv = [sys.executable] + command
        try:
            completed = subprocess.run(argv, cwd=ROOT, text=True,
                                       capture_output=True, timeout=900,
                                       check=False)
            output = (completed.stdout + "\n" + completed.stderr)[-6000:]
            ok = completed.returncode == 0
            outcomes[title] = {"ok": ok, "returncode": completed.returncode,
                               "command": argv, "output_tail": output}
        except (OSError, subprocess.TimeoutExpired) as exc:
            ok = False
            outcomes[title] = {"ok": False, "error": str(exc), "command": argv}
        notes.append(f"- {'✅' if ok else '❌'} {title}")
        if not ok:
            problems.append(finding("local", f"check:{title}",
                                    f"Falhou **{title}**. Consultar o artifact "
                                    "do watchdog para obter a saída completa."))
    return problems, notes, outcomes


def github_review(repo: str, now: datetime) -> tuple[list[dict], list[str], dict]:
    problems = []
    notes = []
    outcomes = {"workflows": {}, "open_prs": 0}
    escaped_repo = quote(repo, safe="/")
    for filename, max_hours in WORKFLOWS.items():
        wf = quote(filename, safe="")
        # GitHub reports the creation timestamp for each registered workflow.
        # Use it only to avoid premature "missing schedule" alerts, never to
        # mask an actually failed/overdue run.
        metadata = api(f"/repos/{escaped_repo}/actions/workflows/{wf}")
        data = api(f"/repos/{escaped_repo}/actions/workflows/{wf}/runs"
                   "?event=schedule&per_page=10")
        label, problem = evaluate_run(filename, data.get("workflow_runs", []),
                                      now, max_hours, repo,
                                      metadata.get("created_at"))
        outcomes["workflows"][filename] = label
        notes.append(f"- {'⚠️' if problem else '✅'} {filename}: {label}")
        if problem:
            problems.append(problem)
    prs = api_pages(f"/repos/{escaped_repo}/pulls?state=open", limit=10)
    outcomes["open_prs"] = len(prs)
    outdated = stale_prs(prs, now, repo)
    problems.extend(outdated)
    notes.append(f"- PRs abertas: {len(prs)} | Sem atualização há 14+ dias: {len(outdated)}")
    return problems, notes, outcomes


def fingerprint(problems: list[dict]) -> str:
    content = sorted(x["id"] for x in problems)
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()[:20]


def render(now: datetime, repo: str, problems: list[dict],
           local_notes: list[str], github_notes: list[str]) -> str:
    signature = fingerprint(problems)
    lines = [
        f"<!-- maintenance-watchdog-signature:{signature} -->",
        "# MrStore — manutenção automática",
        "",
        f"Verificação UTC: {now.strftime('%Y-%m-%d %H:%M')} · "
        f"Problemas operacionais a rever: **{len(problems)}**",
        "",
        "## Ações necessárias",
        "",
    ]
    if problems:
        for item in problems[:40]:
            url = f" ([prova]({item['url']}))" if item["url"] else ""
            lines.append(f"- {item['message']}{url}")
        if len(problems) > 40:
            lines.append(f"- Mais {len(problems) - 40} ocorrências no artifact JSON.")
    else:
        lines.append("- Nenhuma falha detectada nesta seleção de verificações.")
    lines.extend(["", "## Revisão local", "", *local_notes,
                  "", "## Execuções agendadas / PRs", "", *github_notes,
                  "", "## Limites da automação", "",
                  "Este relatório **não certifica** ausência de CVEs, segurança das "
                  "imagens, compatibilidade real no ZimaOS ou funcionamento em hardware.",
                  "Os scanners CVE e o gate de publicação 0 HIGH/CRITICAL continuam "
                  "independentes e obrigatórios.",
                  "A automação não executa merges, upgrades, deployments nem altera "
                  "segredos ou dados persistentes.",
                  ""])
    return "\n".join(lines)


def sync_issue(repo: str, problems: list[dict], body: str) -> str:
    escaped_repo = quote(repo, safe="/")
    issues = api_pages(f"/repos/{escaped_repo}/issues?state=all", limit=20)
    matches = [i for i in issues if i.get("title") == TITLE and
               "pull_request" not in i]
    if len(matches) > 1:
        raise RuntimeError("Watchdog: multiple existing issues; refusing ambiguous update")
    old = matches[0] if matches else None
    if problems:
        if old is None:
            created = api(f"/repos/{escaped_repo}/issues", "POST",
                          {"title": TITLE, "body": body})
            return f"Created issue #{created['number']}"
        if old.get("state") != "open" or fingerprint(problems) not in (old.get("body") or ""):
            api(f"/repos/{escaped_repo}/issues/{old['number']}", "PATCH",
                {"state": "open", "body": body})
            return f"Refreshed issue #{old['number']}"
        return f"Unchanged issue #{old['number']} (no notification spam)"
    if old and old.get("state") == "open":
        api(f"/repos/{escaped_repo}/issues/{old['number']}", "PATCH",
            {"state": "closed", "state_reason": "completed",
             "body": body})
        return f"Closed watchdog issue #{old['number']}; checks recovered"
    return "No findings; no issue needed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync", action="store_true",
                        help="Synchronise the single GitHub tracking issue")
    parser.add_argument("--local-only", action="store_true",
                        help="Run offline checks without querying GitHub")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "out")
    args = parser.parse_args()
    if args.local_only and args.sync:
        parser.error("--sync cannot be combined with --local-only")
    now = datetime.now(timezone.utc)
    repo = os.environ.get("GITHUB_REPOSITORY", "mrpiracy94/MrStore")
    problems, local_notes, local_data = local_review()
    github_notes = []
    remote_data = {}
    if not args.local_only:
        extra, github_notes, remote_data = github_review(repo, now)
        problems.extend(extra)
    body = render(now, repo, problems, local_notes, github_notes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "maintenance-watchdog.md").write_text(
        body + "\n", encoding="utf-8")
    (args.output_dir / "maintenance-watchdog.json").write_text(
        json.dumps({"at": now.isoformat(), "repo": repo, "findings": problems,
                    "local": local_data, "remote": remote_data},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(body)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as file:
            file.write(body)
    if args.sync:
        print(sync_issue(repo, problems, body))
    # The issue tracks failures; make the workflow red until they are resolved.
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
