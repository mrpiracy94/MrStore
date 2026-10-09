"""Read-only evidence collection for issue #45's seven ZimaOS pilot apps.

This performs docker inspect and optional HTTP checks of containers that are
ALREADY installed. No Docker run/up/restart/pull, shell or credentials.
The output intentionally cannot certify installation through ZimaOS, C3, C4,
persistent data or lack of CVEs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler

from catalog import ROOT, apps
from zimaos_runtime_probe import container_snapshot, observed_port

PILOT_APPS = (
    "actual-budget", "uptime-kuma", "nextcloud", "vaultwarden",
    "paperless-ngx", "karakeep", "immich",
)
HOST_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?$")
MANUAL_TESTS = {
    "actual-budget": "Criar orçamento fictício, reiniciar e confirmar dados",
    "uptime-kuma": "Criar monitor de teste, reiniciar e confirmar o histórico",
    "nextcloud": "Testar HTTPS, criar ficheiro de teste e confirmar /config e /data",
    "vaultwarden": "Usar HTTPS, criar cofre fictício e confirmar persistência",
    "paperless-ngx": "Importar documento de teste, verificar Redis, OCR e persistência",
    "karakeep": "Testar login, Chrome, Meilisearch, bookmarks e persistência",
    "immich": "Testar base de dados, Redis, ML, foto fictícia e persistência",
}


def valid_host(value: str) -> bool:
    """Require an uncredentialed hostname/IPv4 only; never accept URL/path/port."""
    return bool(HOST_PATTERN.fullmatch(value) and ".." not in value and
                not value.startswith("-") and not value.endswith("-"))


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never follow an app-provided redirect to a public service.
        return None


def local_http_probe(url, timeout):
    try:
        with build_opener(NoRedirects).open(url, timeout=timeout) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, TimeoutError, OSError):
        return False, None
    return status in (200, 201, 202, 203, 204, 301, 302, 303, 307, 308, 401, 403), status


def inspect_pilot_app(app, host, *, inspector=container_snapshot,
                      prober=local_http_probe, timeout=8.0, skip_http=False):
    services = app.source["services"]
    main = app.metadata["main"]
    port = str(app.metadata.get("port_map", "0"))
    scheme = app.metadata.get("scheme", "http")
    path = app.metadata.get("index", "/")
    summary = {
        "app": app.folder,
        "declared_architectures": app.metadata.get("architectures", []),
        "manifest_version": app.metadata.get("version"),
        "declared_ui_port": port,
        "declared_ui_scheme": scheme,
        "services": {},
        "all_services_running": False,
        "main_port_observed": False,
        "http_reachable": False,
        "http_status": None,
        "c2_candidate": False,
        "installed_via_zimaos_verified": False,
        "functional_c3_verified": False,
        "persistence_verified": False,
        "upgrade_c4_verified": False,
        "manual_functional_test": MANUAL_TESTS[app.folder],
        "manual_verification_required": True,
    }
    main_snapshot = None
    for service, spec in services.items():
        name = spec.get("container_name") if isinstance(spec, dict) else None
        item = {"running": False, "observed": False}
        if isinstance(name, str) and name:
            try:
                snapshot = inspector(name)
                item["observed"] = True
                item["running"] = snapshot.get("running") is True
                if service == main:
                    main_snapshot = snapshot
            except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError):
                item["error"] = "Container unavailable or read-only inspection failed"
        else:
            item["error"] = "Missing fixed container name; manual inspection required"
        summary["services"][service] = item
    summary["all_services_running"] = bool(summary["services"]) and all(
        item["running"] for item in summary["services"].values())
    if main_snapshot is not None and port.isdecimal() and port != "0":
        summary["main_port_observed"] = observed_port(main_snapshot, port)
        if not skip_http and main_snapshot.get("running") is True and summary["main_port_observed"]:
            if scheme in ("http", "https") and isinstance(path, str) and path.startswith("/"):
                # The hostname is intentionally never persisted or printed.
                url = f"{scheme}://{host}:{port}{path}"
                try:
                    ok, status = prober(url, timeout)
                    summary["http_reachable"] = ok is True
                    summary["http_status"] = status if isinstance(status, int) else None
                except (RuntimeError, OSError, ValueError):
                    summary["http_reachable"] = False
    # Only a candidate for human C2 review: source of installation, actual image
    # digest and ZimaOS software version have NOT been independently verified.
    summary["c2_candidate"] = (
        summary["all_services_running"]
        and summary["main_port_observed"]
        and summary["http_reachable"]
    )
    return summary


def make_report(items, host, *, inspector=container_snapshot,
                prober=local_http_probe, timeout=8.0, skip_http=False):
    by_name = {app.folder: app for app in items}
    absent = sorted(set(PILOT_APPS) - set(by_name))
    if absent:
        raise ValueError("Missing pilot manifest(s): " + ", ".join(absent))
    results = [
        inspect_pilot_app(by_name[name], host, inspector=inspector,
                          prober=prober, timeout=timeout, skip_http=skip_http)
        for name in PILOT_APPS
    ]
    return {
        "schema": 1,
        "method": "opt_in_read_only_on_existing_containers",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pilot_total": len(results),
        "c2_candidates": sum(x["c2_candidate"] for x in results),
        "c2_certified": 0,
        "c3_certified": 0,
        "c4_certified": 0,
        "host_recorded": False,
        "image_digest_verified": False,
        "zimaos_store_installation_verified": False,
        "security_audit_passed": "not_evaluated",
        "results": results,
    }


def markdown(data):
    lines = [
        "# MrStore — piloto ZimaOS #45",
        "",
        "**Observação somente de leitura em containers já instalados.**",
        "**Não prova instalação pelo ZimaOS, C3, persistência, migrações ou ausência de CVEs.**",
        "",
        f"Candidatos C2: {data['c2_candidates']}/{data['pilot_total']}. Certificados C2/C3/C4: 0.",
        "",
        "| App | Serviços a correr | Porta UI | HTTP | C2 candidato |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in data["results"]:
        total = len(entry["services"])
        running = sum(x["running"] for x in entry["services"].values())
        lines.append(
            f"| {entry['app']} | {running}/{total} | "
            f"{'sim' if entry['main_port_observed'] else 'não'} | "
            f"{entry['http_status'] if entry['http_reachable'] else 'não comprovado'} | "
            f"{'sim' if entry['c2_candidate'] else 'não'} |")
    lines += ["", "## Comprovação C3 individual (manual, nunca pré-assinalada)", ""]
    for entry in data["results"]:
        lines += [
            f"### {entry['app']}",
            "- [ ] Instalada a partir da MrStore no ZimaOS de ensaio",
            "- [ ] Versão ZimaOS, arquitetura, commit e digest real anotados",
            "- [ ] Auditoria CVE aceite para a imagem/arquitetura instalada",
            f"- [ ] {entry['manual_functional_test']}",
            "- [ ] Dados de teste persistem após reinício controlado",
            "- [ ] Evidência anonimizada e limitações registadas no issue #45",
            "",
        ]
    lines += [
        "C4 exige backup, upgrade e rollback reais em ambiente de teste, nunca nesta ferramenta.",
        "Não publicar IPs, logs, Docker inspect, tokens ou passwords no GitHub.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True, help="Hostname or IPv4, not recorded")
    p.add_argument("--timeout", type=float, default=8)
    p.add_argument("--skip-http", action="store_true",
                   help="Docker-only inspection; cannot produce C2 candidates")
    p.add_argument("--json", type=Path, default=ROOT / "out/zimaos-pilot.json")
    p.add_argument("--md", type=Path, default=ROOT / "out/zimaos-pilot.md")
    args = p.parse_args()
    if not valid_host(args.host):
        p.error("Host must be an IPv4/hostname without scheme, port or credentials")
    if not 0 < args.timeout <= 60:
        p.error("Timeout must be between 0 and 60 seconds")
    report = make_report(apps(), args.host, timeout=args.timeout, skip_http=args.skip_http)
    for output, content in (
        (args.json, json.dumps(report, indent=2, ensure_ascii=False) + "\n"),
        (args.md, markdown(report)),
    ):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    print(f"Piloto C2 observado: {report['c2_candidates']}/{report['pilot_total']}. "
          "C2/C3/C4 certificados: 0. Faltam provas manuais.")
    return 0 if report["c2_candidates"] == report["pilot_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
