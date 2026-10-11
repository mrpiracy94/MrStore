#!/usr/bin/env python3
"""Auditoria estática de TODAS as imagens/apps MrStore e bases Dockerfile.

Não inicia containers, não resolve CVEs e não certifica instalações.
Os avisos históricos são reportados; novas configurações de alto risco
falham na CI. Não expor valores de variáveis de ambiente no relatório.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

import yaml
from catalog import ROOT, apps, image_usage
from privilege_policy import sensitive_host_bind

SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
PLACEHOLDER = re.compile(
    r"^(?:CHANGE[_-]?ME|CHANGEME|YOUR[_-]?(?:PASSWORD|TOKEN|SECRET|API[_-]?KEY)(?:[_-]?HERE)?"
    r"|REPLACE[_-]?ME|INSERT[_-]?(?:TOKEN|PASSWORD)|DEFAULT_PASSWORD|PASSWORD123)$",
    re.I,
)
SECRET_KEY = re.compile(
    r"(?:PASSWORD|PASSWD|_PASS$|_TOKEN$|_SECRET$|_API_KEY$|_KEY_SEED$|JWT_SECRET|AUTH_KEY)",
    re.I,
)
NOT_SECRET = re.compile(r"(?:PASSWORD_ACCESS|PASSWORD_ENABLED|PASSWD_FILE|TOKEN_FILE|PASSWORD_FILE)$", re.I)
# These target ports are intended for ordinary public services, not admin UIs.
# Review the target port, not the host port (which varies per NAS).
PUBLIC_SERVICE_TARGETS = {
    "nginx-proxy-manager": frozenset({80, 443}),
    "qbittorrent": frozenset({6881}),
    "qbittorrent-4": frozenset({6881}),
}

SENSITIVE_WEB = frozenset({
    "dockge", "dozzle", "vaultwarden", "qbittorrent", "qbittorrent-4",
    "nginx-proxy-manager", "node-red", "filebrowser", "open-webui",
    "phpmyadmin", "gitea", "immich", "nextcloud", "kasm", "code-server",
    "webtop", "homeassistant", "esphome", "netdata", "lldap",
    "grafana", "portainer", "paperless-ngx",
})
BLOCK_NEW = frozenset({
    "credential_placeholder", "weak_example_secret", "public_sensitive_ui",
    "privileged", "seccomp_unconfined", "host_network", "sensitive_bind",
    "floating_dockerfile_base", "unresolved_dockerfile_base", "unknown_image_digest",
})
FROM = re.compile(r"(?im)^\s*FROM\s+(?:(?:--platform=\S+)\s+)?(\S+)(?:\s+AS\s+(\S+))?\s*$")


def finding(path: str, service: str, code: str, detail: str, level="warning") -> dict:
    return {"file": path, "service": service, "code": code,
            "detail": detail, "level": level}


def _env_pairs(spec: dict):
    env = spec.get("environment") or []
    if isinstance(env, dict):
        return env.items()
    if isinstance(env, list):
        return (part.split("=", 1) for part in env
                if isinstance(part, str) and "=" in part)
    return ()


def check_manifest(doc: dict, slug: str, digests: dict | None = None) -> list[dict]:
    """Conservative static checks; never include the actual secret value."""
    path = f"Apps/{slug}/docker-compose.yml"
    issues = []
    services = doc.get("services") or {}
    if not isinstance(services, dict):
        raise ValueError(f"{path}: services inválidos")
    for name, spec in services.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: serviço {name} inválido")
        image = spec.get("image")
        if isinstance(image, str):
            if "@sha256:" not in image:
                issues.append(finding(path, name, "floating_image", "Imagem de origem sem digest imutável"))
            if digests is not None:
                expected = digests.get(image)
                if expected is None and "@sha256:" in image:
                    expected = digests.get(image.split("@sha256:", 1)[0])
                if not isinstance(expected, str) or not SHA.fullmatch(expected):
                    issues.append(finding(path, name, "unknown_image_digest", "Imagem sem digest validado na baseline"))
                elif "@sha256:" in image and expected != image.rsplit("@", 1)[1]:
                    issues.append(finding(path, name, "unknown_image_digest", "Digest difere da baseline"))
        else:
            issues.append(finding(path, name, "missing_image", "Serviço sem imagem", "error"))
        for key, value in _env_pairs(spec):
            key = str(key)
            if not SECRET_KEY.search(key) or NOT_SECRET.search(key):
                continue
            if not isinstance(value, str):
                continue
            if PLACEHOLDER.fullmatch(value.strip()):
                issues.append(finding(path, name, "credential_placeholder",
                                      f"Credencial {key} não configurada"))
            elif value.strip().lower() in ("admin", "password", "secret", "123456", "test"):
                issues.append(finding(path, name, "weak_example_secret",
                                      f"Credencial {key} usa valor de exemplo fraco"))
        if spec.get("privileged") is True:
            issues.append(finding(path, name, "privileged", "Contentor privilegiado"))
        if spec.get("network_mode") == "host":
            issues.append(finding(path, name, "host_network", "Acesso à rede do host"))
        if any("seccomp:unconfined" in str(opt).lower() or "seccomp=unconfined" in str(opt).lower()
               for opt in (spec.get("security_opt") or [])):
            issues.append(finding(path, name, "seccomp_unconfined", "Seccomp desativado"))
        for volume in spec.get("volumes") or []:
            source = volume.get("source") if isinstance(volume, dict) and volume.get("type", "bind") == "bind" else (
                str(volume).split(":", 1)[0] if isinstance(volume, str) else None)
            if sensitive_host_bind(source):
                issues.append(finding(path, name, "sensitive_bind",
                                      "Montagem sensível do host: " + str(source)))
        if slug in SENSITIVE_WEB:
            for port in spec.get("ports") or []:
                if isinstance(port, dict):
                    exposed = port.get("published")
                    host = str(port.get("host_ip") or "")
                    protocol = port.get("protocol", "tcp")
                elif isinstance(port, (str, int)):
                    exposed = str(port)
                    host = ""  # conservative: short Compose mapping defaults to all interfaces
                    protocol = "tcp"
                else:
                    continue
                if (exposed and protocol == "tcp" and
                        not (isinstance(port, dict) and str(port.get("target", "")).isdigit() and
                             int(port["target"]) in PUBLIC_SERVICE_TARGETS.get(slug, ()) ) and
                        host not in ("127.0.0.1", "::1")):
                    issues.append(finding(path, name, "public_sensitive_ui",
                                          f"Porta de serviço sensível sem binding local: {exposed}"))
    return issues


def check_dockerfile(text: str, path: str) -> tuple[list[dict], list[str]]:
    issues = []
    stages = set()
    bases = []
    for ordinal, match in enumerate(FROM.finditer(text), start=1):
        base, alias = match.groups()
        if base not in stages and not base.isdigit():
            bases.append(base)
            if "$" in base:
                issues.append(finding(path, f"FROM#{ordinal}", "unresolved_dockerfile_base",
                                      "Imagem base dinâmica; digest não verificável estaticamente"))
            elif "@sha256:" not in base:
                issues.append(finding(path, f"FROM#{ordinal}", "floating_dockerfile_base",
                                      f"Imagem base sem digest imutável: {base}"))
        if alias:
            stages.add(alias)
    return issues, bases


def inventory(root: Path = ROOT) -> dict:
    root = Path(root)
    source = apps(root)
    usage = image_usage(source)
    path = root / "data/image-digests.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    digests = baseline.get("images")
    if not isinstance(digests, dict):
        raise ValueError("Baseline de imagens ausente")
    issues = []
    app_status = {}
    for app in source:
        rows = check_manifest(app.source, app.folder, digests)
        issues.extend(rows)
        app_status[app.folder] = sorted({row["code"] for row in rows})
    dockerfiles = sorted((root / "security/images").glob("*/Dockerfile"))
    bases = {}
    for item in dockerfiles:
        relative = item.relative_to(root).as_posix()
        rows, refs = check_dockerfile(item.read_text(encoding="utf-8"), relative)
        issues.extend(rows)
        bases[relative] = refs
    codes = dict(sorted(Counter(row["code"] for row in issues).items()))
    return {
        "scope": "all_container_images_and_app_manifests",
        "certification": "not_assessed",
        "apps_total": len(source),
        "unique_images_total": len(usage),
        "dockerfiles_total": len(dockerfiles),
        "image_usage": usage,
        "dockerfile_bases": bases,
        "app_findings": app_status,
        "counts_by_rule": codes,
        "findings": issues,
        "limitations": [
            "Static analysis only; not a vulnerability scan or security certification",
            "Published digest does not imply vulnerability-free image",
            "No registry, Docker daemon, host firewall, secrets or runtime configuration inspected",
            "Dockerfile build-time bases may differ from published derivative images",
        ],
    }


def regression_keys(rows: list[dict]) -> set[tuple]:
    keys = set()
    for row in rows:
        if row["code"] in BLOCK_NEW:
            detail = row["detail"] if row["code"] in (
                "public_sensitive_ui", "sensitive_bind",
                "floating_dockerfile_base", "unknown_image_digest",
            ) else ""
            keys.add((row["file"], row["service"], row["code"], detail))
    return keys


def base_findings(root: Path, revision: str, digests: dict) -> list[dict]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", revision, "--", "Apps", "security/images"],
        cwd=root, capture_output=True, text=True, check=True)
    rows = []
    for path in result.stdout.splitlines():
        if not (re.fullmatch(r"Apps/[^/]+/docker-compose\.yml", path)
                or re.fullmatch(r"security/images/[^/]+/Dockerfile", path)):
            continue
        raw = subprocess.run(["git", "show", f"{revision}:{path}"],
                             cwd=root, capture_output=True, text=True, check=True).stdout
        if path.endswith("docker-compose.yml"):
            rows.extend(check_manifest(yaml.safe_load(raw), Path(path).parent.name, digests))
        else:
            entries, _ = check_dockerfile(raw, path)
            rows.extend(entries)
    return rows


def markdown(data: dict, regressions: list[tuple]) -> str:
    header = [
        "# MrStore — auditoria de segurança de todas as imagens",
        "",
        f"Apps: **{data['apps_total']}** · Imagens únicas: **{data['unique_images_total']}** "
        f"· Dockerfiles derivados: **{data['dockerfiles_total']}**",
        "",
        "**Auditoria estática. Não é um teste CVE, de firewall ou runtime.**",
        "",
        "| Ocorrência | Quantidade |", "| --- | ---: |",
    ]
    header += [f"| {k} | {v} |" for k, v in data["counts_by_rule"].items()]
    header += ["", f"Novos riscos bloqueantes face ao Git base: **{len(regressions)}**", "",
               "Os riscos antigos mantêm-se visíveis; requerem migração por aplicação.",
               "O relatório JSON identifica todos os serviços e referências de imagem."]
    return "\n".join(header) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "out/all-image-security.json")
    parser.add_argument("--markdown", type=Path, default=ROOT / "out/all-image-security.md")
    parser.add_argument("--base-sha")
    parser.add_argument("--fail-new-high", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = inventory(args.root)
        new = []
        if args.base_sha:
            digests = json.loads((args.root / "data/image-digests.json").read_text())["images"]
            previous = regression_keys(base_findings(args.root, args.base_sha, digests))
            new = sorted(regression_keys(report["findings"]) - previous)
        if args.fail_new_high and not args.base_sha:
            raise ValueError("Não é possível bloquear regressões sem --base-sha")
        report["new_blocking_findings"] = [
            {"file": p, "service": s, "code": c, "detail": d} for p, s, c, d in new
        ]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report, new), encoding="utf-8")
        print(f"All images: {report['apps_total']} apps / {report['unique_images_total']} "
              f"image refs / {report['dockerfiles_total']} Dockerfiles; "
              f"new high risks: {len(new)}")
        if args.fail_new_high and new:
            for p, s, c, d in new:
                print(f"BLOCK: {p}: {s}: {c}: {d}", file=sys.stderr)
            return 1
    except (ValueError, OSError, subprocess.CalledProcessError, yaml.YAMLError) as exc:
        print(f"Audit failed closed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
