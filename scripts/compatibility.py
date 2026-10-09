"""Read-only ZimaOS launch compatibility inventory; never starts application containers.

A green static result is *not* proof that an app works on a ZimaOS device.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from catalog import ROOT, App, apps


def _published_tcp_ports(service: dict) -> set[str]:
    result: set[str] = set()
    for entry in service.get("ports") or []:
        if isinstance(entry, dict):
            if str(entry.get("protocol", "tcp")).lower() == "tcp":
                published = entry.get("published")
                if published is not None:
                    result.add(str(published))
        elif isinstance(entry, str):
            # Long-form mappings are preferred; support basic "host:container".
            item = entry.rsplit("/", 1)
            if len(item) == 2 and item[1].lower() != "tcp":
                continue
            pair = item[0].split(":")
            if len(pair) >= 2:
                result.add(pair[-2])
    return result


def _environment(service: dict) -> dict[str, str]:
    raw = service.get("environment") or []
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    result = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and "=" in item:
                name, value = item.split("=", 1)
                result[name] = value
    return result


def inspect_app(app: App) -> dict:
    meta = app.metadata
    services = app.source.get("services") or {}
    main = services.get(meta.get("main"), {}) if isinstance(services, dict) else {}
    if not isinstance(main, dict):
        main = {}
    port = str(meta.get("port_map", ""))
    checks: list[dict] = []

    def add(level: str, code: str, description: str) -> None:
        checks.append({"level": level, "code": code, "description": description})

    headless = port == "0"
    scheme = meta.get("scheme", "http")
    if scheme not in ("http", "https"):
        add("review", "unsupported_scheme", "Scheme must be http or https.")
    if not headless:
        if not port.isdecimal() or not (1 <= int(port) <= 65535):
            add("review", "invalid_launch_port", "Invalid published UI port.")
        elif main.get("network_mode") == "host":
            add("review", "host_network_launch", "Host network needs device-specific UI validation.")
        elif port not in _published_tcp_ports(main):
            add("review", "launch_port_mismatch",
                "x-casaos.port_map is not a TCP published port of x-casaos.main.")
    elif main.get("ports"):
        add("info", "headless_with_ports",
            "Headless entry has published ports; confirm if a UI should be offered.")

    index = meta.get("index", "/")
    if not isinstance(index, str) or not index.startswith("/"):
        add("review", "invalid_index", "UI path must begin with /.")

    for service_name, service in (services.items() if isinstance(services, dict) else []):
        if not isinstance(service, dict):
            continue
        env = _environment(service)
        if any("CHANGE_ME" in value or re.search(r"\$\{[A-Z][A-Z0-9_]*:\?", value)
               for value in env.values()):
            add("setup", "required_configuration",
                f"{service_name} requires configuration before first start.")
        for key in ("NEXTAUTH_URL", "AUTH_URL", "PUBLIC_URL", "APP_URL"):
            value = env.get(key, "")
            parsed = urlsplit(value) if value.startswith(("http://", "https://")) else None
            if parsed and parsed.hostname == "zimaos.local":
                try:
                    configured_port = str(parsed.port or (443 if parsed.scheme == "https" else 80))
                except ValueError:
                    add("review", "invalid_public_url", f"{service_name}: malformed {key}.")
                    continue
                if not headless and configured_port != port:
                    add("setup", "public_url_port_mismatch",
                        f"{service_name}: {key} port {configured_port} differs from UI port {port}.")
    if app.folder == "bookstack":
        required = {"APP_URL", "APP_KEY", "DB_HOST", "DB_PORT",
                    "DB_USERNAME", "DB_PASSWORD", "DB_DATABASE"}
        missing = sorted(required - set(_environment(main)))
        if missing:
            add("review", "bookstack_required_environment",
                "BookStack is missing mandatory upstream settings: " + ", ".join(missing))
        if not any(name != meta.get("main") and
                   any(word in name.lower() for word in ("db", "maria", "mysql"))
                   for name in services):
            add("setup", "external_database_required",
                "No database service is defined; configure a reachable external MariaDB/MySQL.")

    if headless:
        status = "headless_not_runtime_tested"
    elif any(x["level"] == "review" for x in checks):
        status = "static_review_required"
    elif any(x["level"] == "setup" for x in checks):
        status = "configuration_required"
    else:
        status = "static_consistent"

    return {
        "app": app.folder, "id": app.app_id,
        "status": status, "ui_port": port,
        "scheme": scheme, "checks": checks,
        "runtime_verified": False,
    }


def inventory(root: Path = ROOT) -> dict:
    results = [inspect_app(app) for app in apps(root)]
    return {
        "method": "offline_static_only",
        "runtime_verified": 0,
        "total": len(results),
        "statuses": dict(sorted(Counter(item["status"] for item in results).items())),
        "apps": results,
    }


def markdown(data: dict) -> str:
    lines = [
        "# MrStore — ZimaOS compatibility inventory", "",
        "**This is a static audit, not a ZimaOS installation test.**",
        f"Apps: {data['total']} | Real-device verification: {data['runtime_verified']}", "",
        "## Static classifications", "",
    ]
    for status, count in data["statuses"].items():
        lines.append(f"- {status}: {count}")
    lines += ["", "## Follow-up actions", "",
              "| App | Classification | Findings |", "| --- | --- | --- |"]
    for item in data["apps"]:
        if item["checks"] or item["status"].startswith(("headless", "static_review")):
            findings = ", ".join(x["code"] for x in item["checks"]) or "No web UI"
            lines.append(f"| {item['app']} | {item['status']} | {findings} |")
    lines += ["", "To mark an app as tested, follow docs/ZIMAOS_COMPATIBILITY.md.",
              "Never treat this report or a successful build as runtime proof.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", type=Path, default=ROOT / "out/compatibility.json")
    parser.add_argument("--md", type=Path, default=ROOT / "out/compatibility.md")
    args = parser.parse_args()
    data = inventory(args.root)
    for target, content in ((args.json, json.dumps(data, indent=2, ensure_ascii=False) + "\n"),
                            (args.md, markdown(data))):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"Offline checks: {data['total']} apps; "
          f"statuses={data['statuses']}; runtime verified=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
