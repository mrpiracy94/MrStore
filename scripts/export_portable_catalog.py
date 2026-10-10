"""Publish portable app manifests for supported Docker-based interfaces.

Consumes only the approved staged manifests and selection report. This does NOT
turn systems with proprietary catalogs into native external-store integrations.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

import yaml

try:
    from export_universal import archive_entries
except ImportError:
    from scripts.export_universal import archive_entries

BASE = "https://mrpiracy94.github.io/MrStore"
PLATFORMS = (
    ("zimaos", "ZimaOS", "native-store", "URL base da loja ZimaOS v2", BASE),
    ("homeio", "Homeio", "catalog-zip-preview", "Adicionar fonte ZIP CasaOS (piloto; requer teste em Homeio real)", BASE + "/store/casaos-homeio-preview.zip"),
    ("casaos", "CasaOS", "catalog-zip-preview", "Testar formato ZIP/Compose na versão instalada; ZIP não certificado como pacote CasaOS v1", BASE + "/store/casaos-homeio-preview.zip"),
    ("umbrelos", "umbrelOS", "adapter-required", "Community App Store exige repositório Git independente com umbrel-app-store.yml; ainda sem adaptador publicado", ""),
    ("cosmos", "Cosmos", "compose-import", "ServApps → Import Docker Compose; rever campos ignorados pelo importador", ""),
    ("portainer", "Portainer", "compose-import", "Stacks → Add stack → Web editor ou Upload (ficheiro Compose aprovado)", ""),
    ("homedock", "HomeDock OS", "packager-import", "Packager → importar Compose CasaOS e gerar pacote HomeDock; .hds ainda não certificado", ""),
    ("olares", "Olares", "adapter-required", "Necessário pacote Olares Application Chart (OAC/Helm) para Market; não aceita Compose como loja nativa", ""),
    ("dockge", "Dockge", "compose-stack", "Adicionar stack com compose.yaml na pasta de stacks; ajustar volumes e portas", ""),
    ("runtipi", "Runtipi", "adapter-required", "App Store própria requer repositório Git com apps/*/config.json, x-runtipi e metadata/logo.jpg", ""),
    ("docker-linux", "Docker / Linux", "compose-cli", "Guardar Compose aprovado e executar docker compose config antes de docker compose up -d", ""),
)


def _label(value, fallback):
    if isinstance(value, dict):
        for locale in ("pt_PT", "en_US"):
            if isinstance(value.get(locale), str) and value[locale].strip():
                return value[locale].strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def portainer_template(slug: str, document: dict) -> dict | None:
    """Export only safely representable, audited single-service Portainer v2 templates."""
    import re
    services = document.get("services", {})
    if not isinstance(services, dict) or len(services) != 1:
        return None
    service = next(iter(services.values()))
    allowed = {"image", "container_name", "restart", "environment",
               "ports", "volumes", "x-casaos"}
    if not isinstance(service, dict) or set(service) - allowed:
        return None
    meta = document["x-casaos"]
    image = service.get("image")
    if not isinstance(image, str) or "@sha256:" not in image:
        return None
    env = service.get("environment") or []
    if isinstance(env, list):
        if any(not isinstance(item, str) or "=" not in item for item in env):
            return None
        values = dict(item.split("=", 1) for item in env)
    elif isinstance(env, dict):
        values = env
    else:
        return None
    if any(not isinstance(k, str) or not isinstance(v, (str, int))
           or "$" + "{" in str(v) or "CHANGE_ME" in str(v)
           or any(word in k.upper() for word in ("PASSWORD", "SECRET", "TOKEN", "API_KEY"))
           for k, v in values.items()):
        return None
    ports = []
    for item in service.get("ports") or []:
        if isinstance(item, dict):
            pub, target = item.get("published"), item.get("target")
            protocol = item.get("protocol", "tcp")
            if pub is None or target is None or protocol not in ("tcp", "udp"):
                return None
            text = f"{pub}:{target}/{protocol}"
        elif isinstance(item, str):
            text = item if "/" in item else item + "/tcp"
        else:
            return None
        if not re.fullmatch(r"[0-9]+:[0-9]+/(tcp|udp)", text):
            return None
        ports.append(text)
    volumes = []
    for item in service.get("volumes") or []:
        if isinstance(item, dict):
            if item.get("type") != "bind" or not isinstance(item.get("source"), str):
                return None
            target = item.get("target")
            if not isinstance(target, str) or not target.startswith("/"):
                return None
            volume = {"container": target, "bind": item["source"]}
            if item.get("read_only"):
                volume["readonly"] = True
        elif isinstance(item, str):
            parts = item.split(":")
            if len(parts) < 2 or len(parts) > 3:
                return None
            if not parts[0].startswith("/") or not parts[1].startswith("/"):
                return None
            volume = {"container": parts[1], "bind": parts[0]}
            if len(parts) == 3 and parts[2] == "ro":
                volume["readonly"] = True
            elif len(parts) == 3 and parts[2] != "rw":
                return None
        else:
            return None
        volumes.append(volume)
    restart = service.get("restart", "unless-stopped")
    if restart not in ("always", "no", "on-failure", "unless-stopped"):
        return None
    return {
        "type": 1, "title": _label(meta.get("title"), slug),
        "description": _label(meta.get("tagline"), slug),
        "image": image, "name": slug,
        "categories": [meta.get("category", "Others")],
        "platform": "linux", "restart_policy": restart,
        "note": "MrStore: rever volumes, portas e backups antes de instalar.",
        "ports": ports, "volumes": volumes,
        "env": [{"name": key, "label": key, "default": str(value)}
                for key, value in sorted(values.items())]
    }


def build(source: Path, selection: Path, dist: Path) -> dict:
    """Atomic fail-closed portable release; does not touch ZimaOS builder output."""
    entries = archive_entries(source, selection)
    slugs = sorted({p.split("/")[1] for p in entries if p.startswith("Apps/")})
    slugs = [slug for slug in slugs if f"Apps/{slug}/docker-compose.yml" in entries]
    if not slugs:
        raise ValueError("No approved Compose apps")
    if (dist / "universal").exists():
        raise ValueError("Refusing to overwrite universal release")
    dist.mkdir(parents=True, exist_ok=True)
    apps = []
    portainer = []
    with tempfile.TemporaryDirectory(prefix=".mrstore-universal-", dir=dist) as tmp:
        work = Path(tmp) / "universal"
        (work / "compose").mkdir(parents=True)
        for slug in slugs:
            content = entries[f"Apps/{slug}/docker-compose.yml"]
            data = yaml.safe_load(content)
            meta = data["x-casaos"]
            template = portainer_template(slug, data)
            if template is not None:
                portainer.append(template)
            file_name = f"compose/{slug}.yml"
            (work / file_name).write_bytes(content)
            apps.append({
                "slug": slug,
                "id": meta["id"],
                "title": _label(meta.get("title"), slug),
                "description": _label(meta.get("tagline"), ""),
                "category": meta.get("category", "Others"),
                "architectures": meta.get("architectures", []),
                "compose": "universal/" + file_name,
            })
        platforms = [
            {"id": ident, "name": name, "method": method, "instructions": guide, "url": url}
            for ident, name, method, guide, url in PLATFORMS
        ]
        catalog = {"version": 1, "security_source": "release-selection.json",
                   "approved_count": len(apps), "portainer_template_count": len(portainer),
                   "platforms": platforms, "apps": apps}
        (work / "portainer-templates.json").write_text(json.dumps(
            {"version": "2", "templates": portainer}, ensure_ascii=False, indent=2)
            + "\n", encoding="utf-8")
        (work / "catalog.json").write_text(json.dumps(
            catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(work, dist / "universal")
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    data = build(args.source, args.selection, args.dist)
    print(f"Universal catalog: {data['approved_count']} approved Compose apps, "
          f"{len(data['platforms'])} target profiles; native support varies by platform")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
