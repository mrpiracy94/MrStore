#!/usr/bin/env python3
"""Triagem determinística de issues para agentes Copilot da MrStore.

Sem token de utilizador, produz apenas relatórios. Nunca faz merge, deploy ou fecha issues.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROUTES = (
    (r"\bcve\b|vulnerabil|trivy|\bsecurity\b|seguran[cç]a", "security-cve", 0),
    (r"image updates|docker image|digest|renovate|depend[eê]nci|builds? antigos", "dependency-updates", 1),
    (r"casaos|homeio|umbrel|runtipi|homedock|olares|portainer|dockge|cosmos|compatib|universal", "platform-compatibility", 2),
    (r"website|site|storefront|frontend|homepage|rebrand|banner|interface", "storefront-ui", 3),
    (r"workflow|actions|watchdog|maintenance|manuten[cç][aã]o|catalog availability|cat[aá]logo p[uú]blico|\bci\b", "operations-ci", 4),
)
# Installations, stateful migrations and validation on real equipment require a human.
HUMAN_ONLY = re.compile(
    r"piloto|device|dispositivo|\bnas\b|instala[cç][aã]o real|certifica|migra[cç][aã]o|backup|restore|rollback",
    re.IGNORECASE,
)
HOLD_LABELS = {"agent:hold", "agent:delegated", "no-agent", "needs-human", "do-not-automate"}
BOT_LOGINS = {"copilot-swe-agent", "copilot-swe-agent[bot]"}
LINKED_ISSUE = re.compile(r"(?<!\w)#([0-9]+)\b")
REPO_NAME = re.compile(r"^[\w.-]+/[\w.-]+$")


def classify(issue: dict) -> tuple[str, int] | None:
    title = str(issue.get("title") or "")
    if HUMAN_ONLY.search(title):
        return None
    for pattern, agent, priority in ROUTES:
        if re.search(pattern, title, re.IGNORECASE):
            return agent, priority
    return None


def queue(issues: list[dict], prs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Only eligible open issues without existing work or human-only risk."""
    referenced = set()
    for pr in prs:
        if pr.get("state") == "open":
            for match in LINKED_ISSUE.findall(
                str(pr.get("title") or "") + "\n" + str(pr.get("body") or "")
            ):
                referenced.add(int(match))
    ready, blocked = [], []
    for issue in issues:
        if issue.get("state") != "open" or issue.get("pull_request"):
            continue
        route = classify(issue)
        if route is None:
            continue
        agent, priority = route
        labels = {str(l.get("name") if isinstance(l, dict) else l).lower()
                  for l in (issue.get("labels") or [])}
        assignees = {str(a.get("login") or "").lower() for a in issue.get("assignees") or []}
        reason = ("linked_open_pr" if issue.get("number") in referenced else
                  "held_or_delegated" if labels & HOLD_LABELS else
                  "copilot_already_assigned" if assignees & BOT_LOGINS else
                  "assigned_to_human" if assignees else None)
        item = {"issue": int(issue["number"]), "title": issue.get("title"),
                "agent": agent, "priority": priority,
                "url": issue.get("html_url", "")}
        (blocked if reason else ready).append(
            {**item, "reason": reason} if reason else item
        )
    ready.sort(key=lambda i: (i["priority"], i["issue"]))
    blocked.sort(key=lambda i: i["issue"])
    return ready, blocked


def gh_api(path: str, *, token: str | None = None, payload: dict | None = None):
    cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json",
           "-H", "X-GitHub-Api-Version: 2022-11-28"]
    if payload is None:
        cmd += ["--method", "GET", "--paginate", "--slurp", path]
    else:
        cmd += ["--method", "POST", path, "--input", "-"]
    env = os.environ.copy()
    if token is not None:
        env["GH_TOKEN"] = token
    proc = subprocess.run(cmd, input=json.dumps(payload) if payload else None,
                          capture_output=True, text=True, env=env, check=False)
    if proc.returncode:
        # gh writes the useful HTTP error to stderr, but CalledProcessError
        # previously hid it and prevented writing a queue report.
        stderr = proc.stderr or ""
        match = re.search(r"\\bHTTP\\s+([1-5]\\d{2})\\b", stderr, re.IGNORECASE)
        code = match.group(1) if match else "unknown"
        detail = next((line.strip() for line in stderr.splitlines()
                       if line.strip().startswith("gh:")), "")
        if not detail:
            detail = (stderr.splitlines() or ["No GitHub API error detail"])[0].strip()
        # Never print user PATs, GitHub App credentials or bearer tokens.
        for secret in (token, env.get("GH_TOKEN"), env.get("GITHUB_TOKEN")):
            if secret:
                detail = detail.replace(secret, "[REDACTED]")
        detail = re.sub(r"(github_pat_|gh[pousr]_|Bearer\\s+)[A-Za-z0-9_\\.-]+",
                        "[REDACTED]", detail, flags=re.IGNORECASE)
        raise RuntimeError(
            f"GitHub API {cmd[-3] if payload is not None else path} "
            f"returned HTTP {code}: {detail[:320]}"
        )
    return json.loads(proc.stdout)


def paginated(repo: str, family: str) -> list[dict]:
    chunks = gh_api(f"/repos/{repo}/{family}?state=open&per_page=100")
    if not isinstance(chunks, list) or any(not isinstance(c, list) for c in chunks):
        raise ValueError(f"GitHub pagination error: {family}")
    return [item for chunk in chunks for item in chunk]


def assignment(repo: str, item: dict, token: str) -> None:
    instructions = (
        f"Usa o agente personalizado {item['agent']} da MrStore e as instruções "
        ".github/copilot-instructions.md. Trabalha apenas neste issue, verifica "
        "PRs relacionados e entrega PR com testes/evidências e blockers. Não "
        "faças merge, publicação ou operações em sistemas reais."
    )
    result = gh_api(f"/repos/{repo}/issues/{item['issue']}/assignees",
                    token=token, payload={
                        "assignees": ["copilot-swe-agent[bot]"],
                        "agent_assignment": {
                            "target_repo": repo, "base_branch": "main",
                            "custom_agent": item["agent"],
                            "custom_instructions": instructions,
                        },
                    })
    names = {str(a.get("login", "")).lower() for a in result.get("assignees") or []}
    if not names & BOT_LOGINS:
        raise RuntimeError(f"GitHub did not confirm Copilot assignment #{item['issue']}")
    # Persistent idempotency guard even after the Copilot assignment ends.
    gh_api(f"/repos/{repo}/issues/{item['issue']}/labels",
           payload={"labels": ["agent:delegated"]})


def render(report: dict) -> str:
    out = ["# MrStore — fila dos agentes Copilot", "",
           f"Modo: **{report['mode']}**; elegíveis: **{len(report['ready'])}**; "
           f"bloqueados: **{len(report['blocked'])}**; "
           f"atribuídos nesta execução: **{len(report['assigned'])}**.", "",
           "A aprovação, o merge e a certificação nunca são automáticos.", ""]
    for item in report["assigned"]:
        out.append(f"- ✅ #{item['issue']} → {item['agent']} (atribuído via API)")
    for item in report["ready"]:
        out.append(f"- ⏳ #{item['issue']} → {item['agent']} — {item['title']}")
    for item in report["blocked"]:
        out.append(f"- ⛔ #{item['issue']} — {item['reason']}")
    if report.get("error"):
        error = report["error"]
        out.extend(["", f"### ERRO: delegação não confirmada no issue #{error['issue']}",
                    f"- Passo: {error['stage']}",
                    f"- Detalhe da API: {error['detail']}",
                    "- Não interpretar este run como delegação concluída. "
                    "Verificar autorização do PAT e disponibilidade do Copilot antes de repetir."])
    if report.get("note"):
        out.extend(["", report["note"]])
    return "\n".join(out) + "\n"


def save_report(report: dict) -> None:
    out = Path("out")
    out.mkdir(exist_ok=True)
    (out / "copilot-queue.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "copilot-queue.md").write_text(render(report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("audit", "auto", "assign"), default="audit")
    parser.add_argument("--max-assignments", type=int, default=2)
    parser.add_argument("--issue", type=int, default=0)
    args = parser.parse_args()
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not REPO_NAME.fullmatch(repo):
        raise SystemExit("GITHUB_REPOSITORY not valid")
    if not 0 <= args.max_assignments <= 5:
        raise SystemExit("max-assignments must be between 0 and 5")
    issues = paginated(repo, "issues")
    prs = paginated(repo, "pulls")
    ready, blocked = queue(issues, prs)
    if args.issue:
        ready = [item for item in ready if item["issue"] == args.issue]
        if not ready:
            raise SystemExit("Selected issue is not eligible (blocked, linked PR or unknown)")
    token = os.getenv("COPILOT_ASSIGN_TOKEN", "")
    wants_assignment = args.mode == "assign" or (args.mode == "auto" and bool(token))
    if args.mode == "assign" and not token:
        raise SystemExit("COPILOT_ASSIGN_TOKEN missing: a user-to-server Copilot token is required")
    report = {"mode": "assign" if wants_assignment else "audit",
              "ready": ready, "blocked": blocked, "assigned": [],
              "note": ("Missing COPILOT_ASSIGN_TOKEN: report only, no Copilot task started."
                       if args.mode == "auto" and not token else "")}
    # Save before performing writes so an API failure never destroys the audit trail.
    save_report(report)
    if wants_assignment:
        for index, item in enumerate(ready[:args.max_assignments]):
            try:
                # Failure stops the run; an unconfirmed assignment is never reported as successful.
                assignment(repo, item, token)
            except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
                report["error"] = {
                    "issue": item["issue"], "stage": "Copilot API assignment",
                    "detail": str(exc)[:450],
                }
                save_report(report)
                print(render(report))
                raise SystemExit(1) from None
            report["assigned"].append(item)
            report["ready"] = ready[index + 1:]
            save_report(report)
    print(render(report))


if __name__ == "__main__":
    main()
