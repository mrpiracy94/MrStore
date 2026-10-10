"""Experimental Olares Application Chart (OAC v0.12.0 / apiVersion v3).

Only trivial single-HTTP-service, audited Compose apps with app-local storage
can be converted automatically. Helm charts are NOT certified Olares apps.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile
import yaml

try:
    from export_universal import archive_entries
except ImportError:
    from scripts.export_universal import archive_entries

REPO = "https://github.com/mrpiracy94/MrStore"
ICON = "https://app.cdn.olares.com/appstore/default/defaulticon.webp"
SERVICE_KEYS = {"image", "container_name", "restart", "environment", "ports", "volumes", "x-casaos"}
APPDATA = "/DATA/AppData/"
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_NAME = re.compile(r"(PASS|SECRET|TOKEN|CREDENTIAL|AUTH|PRIVATE|API_KEY|KEY)", re.I)


def _localized(value, fallback):
    if isinstance(value, dict):
        return value.get("pt_PT") or value.get("en_US") or fallback
    return value if isinstance(value, str) and value.strip() else fallback


def _name(slug: str) -> str:
    """Namespace safe; suffix prevents identity collisions from hyphen stripping."""
    normalized = re.sub("[^a-z0-9]", "", slug.lower())[:18] or "app"
    digest = hashlib.sha256(slug.encode()).hexdigest()[:6]
    return "mr" + normalized + digest


def _static_env(raw: object) -> list[dict] | None:
    if raw is None:
        return []
    if isinstance(raw, dict):
        env = raw
    elif isinstance(raw, list):
        if any(not isinstance(pair, str) or "=" not in pair for pair in raw):
            return None
        env = dict(x.split("=", 1) for x in raw)
    else:
        return None
    output = []
    for name, value in env.items():
        if not isinstance(name, str) or not ENV_NAME.fullmatch(name):
            return None
        if SECRET_NAME.search(name) or not isinstance(value, (str, int)):
            return None
        value = str(value)
        if "CHANGE_ME" in value or "$" in value or "[[" in value:
            return None
        output.append({"name": name, "value": value})
    return sorted(output, key=lambda x: x["name"])


def convert(slug: str, compose: dict) -> dict[str, bytes] | None:
    meta = compose.get("x-casaos", {}) if isinstance(compose, dict) else {}
    services = compose.get("services", {}) if isinstance(compose, dict) else {}
    if not isinstance(meta, dict) or not isinstance(services, dict) or len(services) != 1:
        return None
    service_name = meta.get("main")
    service = services.get(service_name)
    if not isinstance(service, dict) or set(service) - SERVICE_KEYS:
        return None
    if meta.get("scheme", "http") != "http":
        return None
    if meta.get("id") != "io.github.mrpiracy94." + slug:
        return None
    port_map = str(meta.get("port_map", ""))
    mappings = service.get("ports", [])
    if not port_map.isdecimal() or not isinstance(mappings, list) or len(mappings) != 1:
        return None
    port = mappings[0]
    if (not isinstance(port, dict) or port.get("protocol", "tcp") != "tcp"
            or str(port.get("published")) != port_map):
        return None
    internal = port.get("target")
    if not str(internal).isdecimal() or not 1 <= int(internal) <= 65535:
        return None
    env = _static_env(service.get("environment"))
    if env is None:
        return None
    mounts, volumes = [], []
    data_prefix = APPDATA + slug
    for idx, volume in enumerate(service.get("volumes", []) or []):
        if not isinstance(volume, dict) or volume.get("type") != "bind":
            return None
        path = volume.get("source")
        target = volume.get("target")
        if not isinstance(path, str) or not isinstance(target, str) or not target.startswith("/"):
            return None
        if path != data_prefix and not path.startswith(data_prefix + "/"):
            return None
        relative = path[len(data_prefix):].strip("/")
        if not relative or any(seg in (".", "..") for seg in relative.split("/")):
            return None  # Only stable, dedicated subdirectories are supported.
        vname = "appdata" + str(idx)
        mounts.append({"name": vname, "mountPath": target,
                       "readOnly": volume.get("read_only") is True})
        volumes.append({"name": vname, "hostPath": {"path": "__MRSTORE_APPDATA__/" + relative,
                                                    "type": "DirectoryOrCreate"}})

    olname = _name(slug)
    version = str(meta.get("version") or "1.0.0")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?", version):
        return None
    title = _localized(meta.get("title"), slug)[:30]
    tagline = _localized(meta.get("description"), _localized(meta.get("tagline"), slug))
    arches = [a for a in meta.get("architectures", []) if a in ("amd64", "arm64")]
    if not arches:
        return None
    manifest = {
        "olaresManifest.version": "0.12.0", "olaresManifest.type": "app",
        "apiVersion": "v3", "workloadReplicas": {olname: 1},
        "metadata": {"name": olname, "title": title, "description": tagline,
                     "icon": ICON, "version": version,
                     "categories": ["Utilities_v112"]},
        "entrances": [{"name": olname, "host": olname, "port": int(internal),
                       "title": title, "icon": ICON, "authLevel": "private",
                       "openMethod": "default"}],
        "permission": {"appData": bool(volumes), "appCache": False},
        "spec": {"versionName": version, "fullDescription": tagline,
                 "developer": _localized(meta.get("developer"), "MrStore"),
                 "sourceCode": REPO, "website": REPO, "submitter": "MrStore",
                 "locale": ["en-US"], "supportArch": arches, "onlyAdmin": True},
        "options": {"dependencies": [{"name": "olares", "type": "system",
                                     "version": ">=1.12.6-0", "mandatory": True}]}
    }
    container = {"name": olname, "image": service["image"],
                 "ports": [{"name": "http", "containerPort": int(internal),
                            "protocol": "TCP"}]}
    if env:
        container["env"] = env
    if mounts:
        container["volumeMounts"] = mounts
    deploy = {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": olname, "namespace": "__MRSTORE_NAMESPACE__"},
        "spec": {"replicas": 1, "selector": {"matchLabels": {"app": olname}},
                 "template": {"metadata": {"labels": {"app": olname}},
                              "spec": {"containers": [container], "volumes": volumes}}}
    }
    workload = yaml.safe_dump(deploy, sort_keys=False, allow_unicode=True)
    workload = workload.replace("__MRSTORE_NAMESPACE__", "{{ .Release.Namespace }}")
    workload = workload.replace("__MRSTORE_APPDATA__", "{{ .Values.userspace.appData }}")
    svc = {
        "apiVersion": "v1", "kind": "Service",
        "metadata": {"name": olname, "namespace": "__MRSTORE_NAMESPACE__"},
        "spec": {"selector": {"app": olname},
                 "ports": [{"name": "http", "protocol": "TCP",
                            "port": int(internal), "targetPort": int(internal)}]}
    }
    service_yaml = yaml.safe_dump(svc, sort_keys=False).replace(
        "__MRSTORE_NAMESPACE__", "{{ .Release.Namespace }}")
    chart = {"apiVersion": "v2", "type": "application", "name": olname,
             "version": version, "appVersion": version,
             "description": tagline[:150]}
    return {
        "Chart.yaml": (yaml.safe_dump(chart, sort_keys=False, allow_unicode=True)).encode(),
        "OlaresManifest.yaml": (yaml.safe_dump(
            manifest, sort_keys=False, allow_unicode=True)).encode(),
        "values.yaml": b"userspace:\n  appData: ''\n",
        "owners": b"owners:\n- mrpiracy94\n",
        "templates/workload.yaml": (workload + "---\n" + service_yaml).encode(),
    }


def create_tgz(name: str, files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    import gzip
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as archive:
            for path, contents in sorted(files.items()):
                tarinfo = tarfile.TarInfo(name + "/" + path)
                tarinfo.size = len(contents)
                tarinfo.mode = 0o644
                tarinfo.mtime = 0
                archive.addfile(tarinfo, io.BytesIO(contents))
    return buffer.getvalue()


def package(source: Path, selection: Path, output: Path) -> dict:
    inputs = archive_entries(source, selection)
    selection_data = json.loads(selection.read_text(encoding="utf-8"))
    if output.exists():
        raise ValueError("Olares export destination already exists")
    converted = {}
    blocked = {}
    for slug in selection_data["approved"]:
        compose = inputs[f"Apps/{slug}/docker-compose.yml"]
        chart = convert(slug, yaml.safe_load(compose))
        if not chart:
            blocked[slug] = "Compose requires manual OAC/Kubernetes conversion"
            continue
        name = _name(slug)
        if name in converted:
            raise ValueError("Olares chart naming collision")
        converted[name] = chart
    if not converted:
        raise ValueError("No eligible Olares pilot charts")
    output.mkdir(parents=True)
    try:
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, files in sorted(converted.items()):
                for file, data in sorted(files.items()):
                    archive.writestr(name + "/" + file, data)
        (output / "olares-oac-preview.zip").write_bytes(zipped.getvalue())
        for name, files in sorted(converted.items()):
            (output / (name + ".tgz")).write_bytes(create_tgz(name, files))
        report = {"version": 1, "source_approved": len(selection_data["approved"]),
                  "chart_count": len(converted), "charts": sorted(converted),
                  "excluded": blocked, "runtime_verified": False}
        (output / "catalog.json").write_text(json.dumps(
            report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report
    except Exception:
        for f in output.iterdir():
            if f.is_file():
                f.unlink()
        output.rmdir()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    info = package(args.source, args.selection, args.dist / "olares")
    print(f"Olares OAC v0.12 draft: {info['chart_count']}/{info['source_approved']} "
          "charts built; OS install and Helm lint not verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
