"""Experimental Umbrel community-store ZIP from approved, digest-pinned apps only.

Publish the archive to an independent Git repo for real-device testing.
Never auto-install or mark an untested package as compatible.
"""
from __future__ import annotations
import argparse
import json
import os
import tempfile
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

import yaml
try:
    from export_universal import archive_entries
except ImportError:
    from scripts.export_universal import archive_entries


def label(value, fallback):
    if isinstance(value, dict):
        return value.get("pt_PT") or value.get("en_US") or fallback
    return value if isinstance(value, str) and value.strip() else fallback


def convert(slug: str, doc: dict) -> tuple[str, str] | None:
    """Eligible: single HTTP service, one TCP port, local per-app data only."""
    meta, services = doc.get("x-casaos", {}), doc.get("services", {})
    if not isinstance(meta, dict) or not isinstance(services, dict) or len(services) != 1:
        return None
    main = meta.get("main")
    if (main not in services or meta.get("scheme", "http") != "http" or
            not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug) or
            not re.fullmatch(r"[a-zA-Z0-9_-]+", str(main))):
        return None
    service = services[main]
    allowed = {"image", "container_name", "restart", "environment",
               "ports", "volumes", "x-casaos"}
    if not isinstance(service, dict) or set(service) - allowed:
        return None
    published = str(meta.get("port_map", ""))
    ports = service.get("ports", [])
    if not published.isdecimal() or not isinstance(ports, list) or len(ports) != 1:
        return None
    entry = ports[0]
    if not isinstance(entry, dict) or str(entry.get("published")) != published or entry.get("protocol", "tcp") != "tcp":
        return None
    internal = entry.get("target")
    if not str(internal).isdecimal() or not (1 <= int(internal) <= 65535):
        return None
    volumes = []
    prefix = "/DATA/AppData/" + slug
    for mount in service.get("volumes") or []:
        if not isinstance(mount, dict) or mount.get("type") != "bind":
            return None
        source, target = mount.get("source"), mount.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            return None
        if source != prefix and not source.startswith(prefix + "/"):
            return None
        relative = source[len(prefix):].lstrip("/")
        if ".." in relative.split("/") or not target.startswith("/"):
            return None
        item = {"type": "bind", "source": "$" + "{APP_DATA_DIR}" + ("/" + relative if relative else ""),
                "target": target}
        if mount.get("read_only") is True:
            item["read_only"] = True
        volumes.append(item)
    # Never embed static credentials or unresolved Compose interpolation in
    # portable community-store packages. They require a per-platform setup UI.
    environment = service.get("environment", {})
    if isinstance(environment, list):
        if any(not isinstance(item, str) or "=" not in item for item in environment):
            return None
        environment = dict(item.split("=", 1) for item in environment)
    if not isinstance(environment, dict):
        return None
    for key, value in environment.items():
        if not isinstance(key, str) or not isinstance(value, (str, int)):
            return None
        if re.search(r"PASS|SECRET|TOKEN|CREDENTIAL|AUTH|PRIVATE|API_KEY|KEY", key, re.I):
            return None
        if any(marker in str(value) for marker in ("CHANGE_ME", "${", "[[")):
            return None
    app_id = "mrstore-" + slug
    normalized = {k: v for k, v in service.items()
                  if k not in ("ports", "volumes", "container_name", "x-casaos")}
    if volumes:
        normalized["volumes"] = volumes
    compose = {"version": "3.7", "services": {
        "app_proxy": {"environment": {"APP_HOST": app_id + "_" + main + "_1",
                                      "APP_PORT": int(internal)}},
        main: normalized,
    }}
    repo = "https://github.com/mrpiracy94/MrStore"
    icon = meta.get("icon")
    if not isinstance(icon, str) or not icon.startswith("https://"):
        icon = "https://mrpiracy94.github.io/MrStore/assets/mark.svg"
    tagline = label(meta.get("tagline"), "Aplicação self-hosted MrStore")
    manifest = {
        "manifestVersion": 1, "id": app_id,
        "name": label(meta.get("title"), slug), "tagline": tagline,
        "icon": icon, "category": "Utilities",
        "version": str(meta.get("version", "1.0.0")),
        "port": int(internal),
        "description": label(meta.get("description"), tagline),
        "developer": str(meta.get("developer", "MrStore")),
        "website": repo, "submitter": "MrStore",
        "submission": repo, "repo": repo, "support": repo + "/issues",
        "dependencies": [], "path": "", "defaultUsername": "",
        "defaultPassword": "",
    }
    return (yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
            yaml.safe_dump(compose, sort_keys=False, allow_unicode=True))


def package(source: Path, selection: Path, output: Path) -> dict:
    entries = archive_entries(source, selection)
    slugs = sorted({p.split("/")[1] for p in entries if p.startswith("Apps/")})
    content = {"umbrel-app-store.yml": yaml.safe_dump({"id": "mrstore", "name": "MrStore"})}
    excluded = []
    for slug in slugs:
        raw = entries.get(f"Apps/{slug}/docker-compose.yml")
        result = convert(slug, yaml.safe_load(raw)) if raw else None
        if not result:
            excluded.append(slug)
            continue
        content[f"mrstore-{slug}/umbrel-app.yml"] = result[0]
        content[f"mrstore-{slug}/docker-compose.yml"] = result[1]
    if len(excluded) == len(slugs):
        raise ValueError("No conservatively eligible Umbrel applications")
    if output.exists():
        raise ValueError("Refusing to overwrite Umbrel preview")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".mrstore-preview-", suffix=".zip",
                                     dir=output.parent, delete=False) as temp:
        tmp = Path(temp.name)
    try:
        with ZipFile(tmp, "w", ZIP_DEFLATED) as archive:
            for name, content_text in sorted(content.items()):
                archive.writestr(name, content_text.encode("utf-8"))
        with ZipFile(tmp) as verified:
            if verified.testzip() is not None:
                raise ValueError("Umbrel preview ZIP failed integrity verification")
        os.replace(tmp, output)
    finally:
        tmp.unlink(missing_ok=True)
    return {"source_approved": len(slugs), "draft_converted": len(slugs) - len(excluded),
            "excluded": excluded, "real_device_tested": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--selection", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    opts = p.parse_args()
    print(json.dumps(package(opts.source, opts.selection, opts.output),
                     ensure_ascii=False))
