#!/usr/bin/env python3
"""Read-only GitHub Actions issue triage for MrStore.

Produces bounded JSON and Markdown evidence for human review. Does not:
change issue state, start builds, deploy, alter Compose, or declare CVEs fixed.
Only workflow/job metadata are read; raw logs (which could contain secrets)
are deliberately not downloaded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

TRACKS = {
    "cve": {
        "workflows": ("cve-scan.yml", "retry-inconclusive-cves.yml"),
        "next": "Consultar o relatório Trivy e a cobertura AMD64/ARM64; corrigir a imagem e repetir a verificação. Nunca tratar scans parciais como 0 CVE.",
    },
    "publication": {
        "workflows": ("catalog-uptime.yml", "publish.yml"),
        "next": "Conferir store.json, index.json, release-status.json, seleção aprovada e o último build/publish; não fabricar evidência de segurança.",
    },
    "updates": {
        "workflows": ("update-monitor.yml", "image-freshness.yml"),
        "next": "Analisar digests, erros de registry e versões; testar volumes/portas antes de propor atualização. Um digest novo não prova compatibilidade.",
    },
    "maintenance": {
        "workflows": ("maintenance-watchdog.yml", "catalog-uptime.yml"),
        "next": "Verificar execução agendada, falha exata e idade do último run; não encerrar o watchdog sem nova execução concluída.",
    },
    "security": {
        "workflows": ("verify-socket-proxy-readonly.yml", "update-migration-gate.yml"),
        "next": "Rever permissões Docker, paths sensíveis e isolamento; confirmar em testes reais quando requerido.",
    },
    "migrations": {
        "workflows": ("update-migration-gate.yml", "validate.yml"),
        "next": "Exigir backup, restore e testes de persistência num NAS antes de migrar uma base de dados.",
    },
    "compatibility": {
        "workflows": ("validate.yml",),
        "next": "CI estático não é instalação C3 no ZimaOS; recolher evidência no NAS e manter issue aberto até essa validação.",
    },
    "dependencies": {
        "workflows": ("update-monitor.yml", "validate.yml"),
        "next": "Rever propostas Renovate e falhas de resolução, sem aceitar upgrades major automaticamente.",
    },
    "ci": {
        "workflows": ("validate.yml", "publish.yml"),
        "next": "Abrir o run e o job falhado, corrigir a causa e voltar a executar; não ignorar gates de segurança.",
    },
}
FOCI = ("all",) + tuple(TRACKS)
ISSUE_MAP = {
    3: "dependencies", 4: "cve", 8: "updates", 11: "cve",
    14: "cve", 15: "cve", 19: "cve", 20: "cve",
    21: "cve", 22: "cve", 34: "cve", 45: "compatibility",
    53: "security", 58: "migrations", 64: "updates",
    94: "publication", 95: "maintenance",
}
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHARD = re.compile(r"shard\s+([0-7])\b", re.IGNORECASE)


def clean(value: object, max_length: int = 180) -> str:
    """Do not let issue text inject new Markdown headings or links."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"[\[\]<>|]", "", text)
    return text[:max_length]


def classify(issue: dict) -> str:
    number = issue.get("number")
    if type(number) is int and number in ISSUE_MAP:
        return ISSUE_MAP[number]
    title = str(issue.get("title", "")).lower()
    if "cve" in title or "vulnerabil" in title:
        return "cve"
    if "uptime" in title or "catalog availability" in title or "public catalog" in title:
        return "publication"
    if "watchdog" in title or "maintenan" in title:
        return "maintenance"
    if "postgres" in title or "migr" in title:
        return "migrations"
    if "socket" in title or "privileg" in title or "permission" in title:
        return "security"
    if "zimaos" in title or "compatib" in title:
        return "compatibility"
    if "renovate" in title or "dependenc" in title:
        return "dependencies"
    if "update" in title or "image" in title:
        return "updates"
    return "ci"


def relevant_workflows(focus: str, selected: list[dict]) -> list[str]:
    if focus != "all":
        return list(TRACKS[focus]["workflows"])
    categories = {classify(item) for item in selected}
    return sorted({workflow for cat in categories for workflow in TRACKS[cat]["workflows"]})


def failed_steps(jobs: list[dict]) -> list[dict]:
    result = []
    for job in jobs:
        if job.get("conclusion") not in ("failure", "timed_out", "action_required"):
            continue
        steps = [clean(step.get("name"), 100)
                 for step in job.get("steps", [])
                 if step.get("conclusion") in ("failure", "timed_out", "action_required")]
        result.append({
            "job": clean(job.get("name"), 120),
            "steps": steps[:8],
            "url": job.get("html_url", ""),
        })
    return result[:8]


def run_record(workflow: str, runs: list[dict], jobs: list[dict] | None = None) -> dict:
    if not runs:
        return {"workflow": workflow, "state": "sem_execucao", "conclusion": None,
                "url": "", "run_id": None, "failed_jobs": []}
    latest = max(runs, key=lambda run: run.get("created_at", ""))
    status = latest.get("status")
    conclusion = latest.get("conclusion")
    state = ("a_decorrer" if status != "completed"
             else "falhou" if conclusion in ("failure", "timed_out", "action_required")
             else "concluido" if conclusion == "success"
             else "inconclusivo")
    return {"workflow": workflow, "state": state, "conclusion": conclusion,
            "url": latest.get("html_url", ""),
            "created_at": latest.get("created_at"),
            "run_id": latest.get("id"),
            "failed_jobs": failed_steps(jobs or [])}


def build_report(repo: str, issues: list[dict], prs: list[dict],
                 workflow_runs: dict[str, list[dict]],
                 job_records: dict[int, list[dict]] | None = None,
                 focus: str = "all", issue_number: int | None = None,
                 generated_at: str | None = None) -> dict:
    if focus not in FOCI:
        raise ValueError("Invalid triage focus")
    open_issues = [item for item in issues
                   if item.get("state") == "open" and not item.get("pull_request")]
    selected = [item for item in open_issues
                if (issue_number is None or item.get("number") == issue_number)
                and (focus == "all" or classify(item) == focus)]
    if issue_number is not None and not selected:
        raise ValueError("Selected issue is not open or does not match focus")

    checked_workflows = relevant_workflows(focus, selected)
    jobs = job_records or {}
    workflow = [run_record(name, workflow_runs.get(name, []),
                           jobs.get(workflow_runs[name][0].get("id"), [])
                           if workflow_runs.get(name) else [])
                for name in checked_workflows]
    summaries = []
    for item in selected:
        cat = classify(item)
        entry = {"number": item["number"], "title": clean(item.get("title"), 140),
                 "url": f"https://github.com/{repo}/issues/{item['number']}",
                 "category": cat, "next_action": TRACKS[cat]["next"],
                 "workflow_names": list(TRACKS[cat]["workflows"])}
        match = SHARD.search(item.get("title", ""))
        if match and cat == "cve":
            entry["shard"] = int(match.group(1))
        summaries.append(entry)
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "repository": repo, "focus": focus, "issue_number": issue_number,
        "open_issues_observed": len(open_issues),
        "selected_issues": summaries,
        "open_prs_observed": sum(1 for item in prs if item.get("state") == "open"),
        "workflow_runs": workflow,
        "limitations": [
            "A consulta é apenas informativa e não fecha issues nem executa atualizações.",
            "Um workflow concluído com sucesso não prova ausência de CVEs ou compatibilidade real.",
            "Resultados GitHub Actions não substituem ensaios C3 num NAS ZimaOS.",
            "Apenas os últimos runs da main são consultados; a auditoria é um instantâneo.",
        ],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# MrStore — relatório de diagnóstico dos issues",
        "",
        f"**Gerado:** {report['generated_at']}  ",
        f"**Repositório:** {report['repository']}  ",
        f"**Área:** {report['focus']}  ",
        f"**Issues abertos observados:** {report['open_issues_observed']} "
        f"(**{len(report['selected_issues'])}** selecionados)  ",
        f"**PRs abertas observadas:** {report['open_prs_observed']}",
        "",
        "## Issues e próximos passos",
        "",
    ]
    if not report["selected_issues"]:
        lines.append("Nenhum issue aberto corresponde ao filtro solicitado.")
    for item in report["selected_issues"]:
        title = clean(item["title"])
        lines.append(f"### [#{item['number']} — {title}]({item['url']})")
        lines.append(f"- Área: **{item['category']}**")
        if "shard" in item:
            lines.append(f"- Shard CVE: **{item['shard']}** (não confundir com ausência de vulnerabilidades)")
        lines.append(f"- Próxima ação: {item['next_action']}")
        lines.append("- Workflows relacionados: " + ", ".join(
            f"[{clean(w)}](https://github.com/{report['repository']}/actions/workflows/{w})"
            for w in item["workflow_names"]))
        lines.append("")
    lines.extend(["## Últimos runs da branch main (metadados)", "",
                  "| Workflow | Resultado observado | Job / passo falhado |",
                  "| --- | --- | --- |"])
    for run in report["workflow_runs"]:
        label = clean(run["workflow"])
        link = f"[{label}]({run['url']})" if run["url"] else label
        result = clean(run["state"] + (" / " + str(run["conclusion"]) if run["conclusion"] else ""))
        failures = "; ".join(
            clean(job["job"] + ": " + (", ".join(job["steps"]) if job["steps"] else "passo não identificado"), 180)
            for job in run["failed_jobs"]) or "—"
        lines.append(f"| {link} | {result} | {failures} |")
    lines.extend(["", "## Limites", ""])
    lines.extend("- " + item for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def get_json(repo: str, path: str, token: str, timeout: int = 30):
    if not path.startswith(f"/repos/{repo}/"):
        raise ValueError("Only same-repository GitHub API reads are permitted")
    request = Request("https://api.github.com" + path, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "User-Agent": "MrStore-Actions-ReadOnly-Triage",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def list_pages(repo: str, path: str, token: str, key: str | None = None,
               max_pages: int = 3) -> list[dict]:
    found = []
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in path else "?"
        data = get_json(repo, f"{path}{separator}per_page=100&page={page}", token)
        batch = data.get(key, []) if key else data
        if not isinstance(batch, list):
            raise ValueError("Unexpected GitHub pagination response")
        found.extend(batch)
        if len(batch) < 100:
            return found
    raise ValueError("GitHub pagination limit reached; no incomplete report produced")


def collect(repo: str, token: str, focus: str = "all",
            issue_number: int | None = None, get=get_json) -> dict:
    issues = list_pages(repo, f"/repos/{repo}/issues?state=open", token)
    prs = list_pages(repo, f"/repos/{repo}/pulls?state=open", token)
    selected = [item for item in issues if not item.get("pull_request")
                and (issue_number is None or item.get("number") == issue_number)
                and (focus == "all" or classify(item) == focus)]
    workflows = relevant_workflows(focus, selected)
    runs = {}
    jobs = {}
    for workflow in workflows:
        encoded = quote(workflow, safe="")
        response = get(repo, f"/repos/{repo}/actions/workflows/{encoded}/runs"
                       "?branch=main&per_page=5", token)
        entries = response.get("workflow_runs", [])
        if not isinstance(entries, list):
            raise ValueError("Malformed workflow runs: " + workflow)
        entries = sorted(entries, key=lambda row: row.get("created_at", ""), reverse=True)
        runs[workflow] = entries
        if entries and entries[0].get("conclusion") in ("failure", "timed_out", "action_required"):
            run_id = entries[0].get("id")
            if type(run_id) is not int:
                raise ValueError("Missing run ID for failed workflow: " + workflow)
            data = get(repo, f"/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", token)
            if not isinstance(data.get("jobs"), list):
                raise ValueError("Invalid job response for failed workflow")
            jobs[run_id] = data["jobs"]
    return build_report(repo, issues, prs, runs, jobs, focus, issue_number)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "mrpiracy94/MrStore"))
    parser.add_argument("--focus", choices=FOCI, default="all")
    parser.add_argument("--issue", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("out/issue-triage"))
    args = parser.parse_args()
    if not REPO.fullmatch(args.repo):
        parser.error("Expected owner/repository")
    if args.issue is not None and args.issue <= 0:
        parser.error("Issue number must be positive")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        parser.error("GITHUB_TOKEN (read-only) is required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = collect(args.repo, token, args.focus, args.issue)
        markdown = render_markdown(report)
        status = 0
    except (ValueError, KeyError, TypeError, HTTPError, URLError, TimeoutError) as error:
        # No fabricated success report on network/API failure. Keep diagnostic artifacts.
        report = {"repository": args.repo, "focus": args.focus, "error": clean(error, 350),
                  "state": "incomplete", "generated_at": datetime.now(timezone.utc).isoformat()}
        markdown = ("# MrStore — diagnóstico inconclusivo\n\n"
                    "A consulta à API falhou; não foram considerados issues resolvidos.\n\n"
                    f"Erro: {clean(error, 350)}\n")
        status = 1
    (args.output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "report.md").write_text(markdown, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(markdown)
    print(markdown)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
