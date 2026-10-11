#!/usr/bin/env python3
"""Export reviewed MrStore packages for several platforms, without installing anything.

Apps/ remains the only source catalog. Package eligibility is NOT a security
certification or evidence of a successful installation on physical hardware.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
from pathlib import Path
import re
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import yaml

from catalog import ROOT, App, apps

PLATFORMS = ("umbrel", "casaos", "homeio", "docker")
SOURCE_PREFIX = "/DATA/AppData/"
IMAGE_MUTABLE = re.compile(r":(?:latest|stable|edge|main|nightly)(?:@|$)", re.I)
DANGEROUS_ENV = re.compile(r"(?:CHANGE_ME|CHANGEME|REPLACE_ME|YOUR_PASSWORD)", re.I)
SECRET_ENV = re.compile(r"(?:^|_)(?:PASSWORD|SECRET|TOKEN|API_KEY|PASSWD|JWT_KEY)(?:$|_)", re.I)
BLOCKED_MOUNTS = ("/var/run/docker.sock", "/run/docker.sock", "/etc", "/proc", "/sys", "/dev", "/root")
CATEGORY_MAP = {
    "Media": "media", "Productivity": "productivity", "Home": "automation",
    "Networking": "networking", "Developer": "development",
    "AI": "ai", "Finance": "finance", "Social": "social", "Others": "utilities",
}


def _environment(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    if isinstance(value, list):
        return dict(x.split("=", 1) for x in value if isinstance(x, str) and "=" in x)
    return {}


def _volumes(value: object) -> list[tuple[str, str]]:
    """Return sources and targets without interpreting untrusted compose directives."""
    result = []
    if not isinstance(value, list):
        return result
    for item in value:
        if isinstance(item, dict):
            if item.get("type", "volume") == "bind":
                result.append((str(item.get("source", "")), str(item.get("target", ""))))
            elif item.get("type") == "volume":
                result.append((str(item.get("source", "")), str(item.get("target", ""))))
        elif isinstance(item, str):
            parts = item.split(":")
            if len(parts) >= 2:
                result.append((parts[0], parts[1]))
    return result


def _ui_binding(app: App) -> tuple[int, int] | None:
    services = app.source.get("services") or {}
    main = services.get(app.metadata.get("main")) if isinstance(services, dict) else None
    if not isinstance(main, dict):
        return None
    published = str(app.metadata.get("port_map", ""))
    ports = main.get("ports") or []
    if not isinstance(ports, list):
        return None
    found = []
    for port in ports:
        if isinstance(port, dict):
            if str(port.get("published")) == published and str(port.get("protocol", "tcp")).lower() == "tcp":
                found.append(port.get("target"))
        elif isinstance(port, str):
            parts = port.split(":")
            if len(parts) >= 2 and parts[-2] == published and not port.endswith("/udp"):
                found.append(parts[-1].split("/")[0])
    if len(found) != 1:
        return None
    try:
        target, host = int(found[0]), int(published)
    except (TypeError, ValueError):
        return None
    if not (0 < target < 65536 and 0 < host < 65536):
        return None
    return target, host


def blockers(app: App, platform: str) -> list[str]:
    """Conservative, static portability policy; never treated as CVE clearance."""
    if platform not in PLATFORMS:
        raise ValueError("Unknown platform: " + platform)
    reasons = set()
    services = app.source.get("services")
    if not isinstance(services, dict) or not services:
        return ["invalid_services"]
    if _ui_binding(app) is None:
        reasons.add("ui_port_not_mapped")
    if platform == "umbrel" and len(services) != 1:
        reasons.add("umbrel_multiservice_manual_port")
    if any(k in app.source for k in ("include", "extends", "build")):
        reasons.add("unsupported_compose_extension")
    for name, service in services.items():
        if not isinstance(service, dict):
            reasons.add("invalid_service")
            continue
        image = service.get("image")
        if not isinstance(image, str) or not image or IMAGE_MUTABLE.search(image):
            reasons.add("mutable_or_missing_image")
        if service.get("privileged") or service.get("devices") or service.get("cap_add"):
            reasons.add("elevated_privileges")
        if service.get("network_mode") in ("host", "service:docker") or service.get("pid") == "host":
            reasons.add("host_namespace")
        if service.get("security_opt") or service.get("userns_mode") == "host":
            reasons.add("security_overrides")
        if any(k in service for k in ("build", "extends", "volumes_from", "secrets", "configs")):
            reasons.add("manual_dependencies")
        env = _environment(service.get("environment"))
        if DANGEROUS_ENV.search(json.dumps(env)):
            reasons.add("placeholder_credentials")
        for key, value in env.items():
            if SECRET_ENV.search(key) and value and not value.startswith("$"):
                reasons.add("static_credentials_review")
        for source, target in _volumes(service.get("volumes")):
            if any(source == s or source.startswith(s + "/") for s in BLOCKED_MOUNTS):
                reasons.add("sensitive_host_mount")
            if not (source == SOURCE_PREFIX + app.folder or
                    source.startswith(SOURCE_PREFIX + app.folder + "/")):
                reasons.add("nonportable_storage")
            if not target.startswith("/") or ".." in Path(target).parts:
                reasons.add("invalid_volume_target")
        if service.get("volumes") and len(_volumes(service["volumes"])) != len(service["volumes"]):
            reasons.add("unhandled_volumes")
        if platform == "umbrel":
            if not isinstance(service.get("ports"), list) or len(service["ports"]) != 1:
                reasons.add("umbrel_additional_ports")
            if service.get("network_mode") or service.get("networks") or service.get("links"):
                reasons.add("umbrel_custom_network")
    return sorted(reasons)


def _translate_bind(source: str, slug: str, *, umbrel: bool) -> str:
    root = SOURCE_PREFIX + slug
    if source != root and not source.startswith(root + "/"):
        raise ValueError("Cannot safely relocate " + source)
    suffix = source[len(root):].lstrip("/")
    base = "\${APP_DATA_DIR}/data" if umbrel else "./data"
    return base + ("/" + suffix if suffix else "")


def _native_compose(app: App, platform: str) -> dict:
    reasons = blockers(app, platform)
    if reasons:
        raise ValueError(f"{app.folder}: {platform} blocked: {', '.join(reasons)}")
    output = copy.deepcopy(app.source)
    output.pop("x-casaos", None)
    output.pop("name", None)
    for service in output["services"].values():
        service.pop("x-casaos", None)
        service.pop("container_name", None)
        for mount in service.get("volumes") or []:
            if isinstance(mount, dict) and mount.get("type") == "bind":
                mount["source"] = _translate_bind(str(mount["source"]), app.folder, umbrel=platform == "umbrel")
            elif isinstance(mount, str):
                raise ValueError("Short-format binds require manual review")
        if platform == "umbrel":
            service.pop("ports", None)
    if platform == "umbrel":
        target, _ = _ui_binding(app)
        slug = "mrstore-" + app.folder
        main = app.metadata["main"]
        output["services"] = {
            "app_proxy": {"environment": {
                "APP_HOST": f"{slug}_{main}_1",
                "APP_PORT": target,
            }},
            **output["services"],
        }
    return output


def _umbrel_metadata(app: App) -> dict:
    meta = app.metadata
    port = _ui_binding(app)
    if port is None:
        raise ValueError("Missing UI port")
    en = lambda value: (value.get("en_US") or next(iter(value.values()), "")) if isinstance(value, dict) else ""
    return {
        "manifestVersion": 1,
        "id": "mrstore-" + app.folder,
        "name": en(meta.get("title")) or app.folder,
        "tagline": en(meta.get("tagline")) or "MrStore community package",
        "icon": meta.get("icon", ""),
        "category": CATEGORY_MAP.get(meta.get("category"), "utilities"),
        "version": str(meta.get("version", "1.0.0")),
        "port": port[1],
        "description": en(meta.get("description")) or "Community maintained package. Check security and persistence before use.",
        "developer": str(meta.get("developer") or "Community"),
        "website": str(meta.get("website") or "https://github.com/mrpiracy94/MrStore"),
        "submitter": "MrStore",
        "submission": "https://github.com/mrpiracy94/MrStore",
        "repo": str(meta.get("repo") or "https://github.com/mrpiracy94/MrStore"),
        "support": "https://github.com/mrpiracy94/MrStore/issues",
        "gallery": [],
        "releaseNotes": "MrStore adapter preview. Not verified on a real umbrelOS installation.",
        "dependencies": [],
        "path": str(meta.get("index") or "/"),
        "defaultUsername": "",
        "defaultPassword": "",
    }


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_zip(path: Path, contents: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(contents.items()):
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError("Unsafe archive path")
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def _read_pilots(root: Path, available: set[str]) -> dict[str, list[str]]:
    data = json.loads((root / "data/platform-pilots.json").read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("platforms"), dict):
        raise ValueError("Invalid pilot schema")
    chosen = {}
    for platform in PLATFORMS:
        names = data["platforms"].get(platform)
        if not isinstance(names, list) or not names or any(not isinstance(x, str) for x in names):
            raise ValueError("Pilot list missing for " + platform)
        if len(names) != len(set(names)) or not set(names) <= available:
            raise ValueError("Pilot list contains duplicates or unknown apps for " + platform)
        chosen[platform] = names
    return chosen


def _matrix(items: list[App], chosen: dict[str, list[str]]) -> dict:
    result = []
    for app in items:
        row = {"app": app.folder, "id": app.app_id, "architectures": app.metadata.get("architectures", []),
               "runtime_verified": False, "platforms": {}}
        for platform in PLATFORMS:
            issues = blockers(app, platform)
            row["platforms"][platform] = {
                "status": "blocked" if issues else ("pilot_exportable" if app.folder in chosen[platform] else "review_required"),
                "blockers": issues, "selected_for_pilot": app.folder in chosen[platform],
                "device_tested": False,
            }
        result.append(row)
    return {"schema": 1, "source_apps": len(items),
            "certification": "not_assessed", "device_installations_verified": 0,
            "apps": result}


def export(root: Path, destination: Path, selected: str = "all") -> dict:
    items = apps(root)
    by_name = {app.folder: app for app in items}
    chosen = _read_pilots(root, set(by_name))
    matrix = _matrix(items, chosen)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "compatibility.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for platform in PLATFORMS:
        if selected not in ("all", platform):
            continue
        output_dir = destination / platform
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in chosen[platform]:
            issues = blockers(by_name[name], platform)
            if issues:
                raise ValueError(f"Explicitly selected {name} for {platform} but blocked: {', '.join(issues)}")
        if platform == "umbrel":
            _write_yaml(output_dir / "umbrel-app-store.yml", {"id": "mrstore", "name": "MrStore"})
            for name in chosen[platform]:
                app = by_name[name]
                folder = output_dir / ("mrstore-" + name)
                _write_yaml(folder / "umbrel-app.yml", _umbrel_metadata(app))
                _write_yaml(folder / "docker-compose.yml", _native_compose(app, platform))
        elif platform == "docker":
            for name in chosen[platform]:
                _write_yaml(output_dir / name / "docker-compose.yml", _native_compose(by_name[name], platform))
        else:
            files: dict[str, bytes] = {}
            for name in chosen[platform]:
                app = by_name[name]
                files[f"Apps/{name}/docker-compose.yml"] = app.path.read_bytes()
            for filename in ("store-config.json", "supported-languages.json", "category-list.json"):
                files[filename] = (root / filename).read_bytes()
            files["README-COMPATIBILITY.txt"] = (
                "MrStore " + platform + " preview package\n"
                "Only explicitly reviewed pilot packages. No real-device install is certified.\n"
                "Check container images, credentials, volumes, persistence and CVEs before installing.\n"
                "Original source: https://github.com/mrpiracy94/MrStore\n"
            ).encode("utf-8")
            _write_zip(output_dir / ("mrstore-" + platform + ".zip"), files)
    return matrix


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--output", type=Path, default=ROOT / "out" / "platforms")
    p.add_argument("--platform", choices=("all",) + PLATFORMS, default="all")
    args = p.parse_args()
    result = export(args.root, args.output, args.platform)
    print(f"Analysed {result['source_apps']} apps; generated {args.platform} preview; "
          "installation on physical devices NOT verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
