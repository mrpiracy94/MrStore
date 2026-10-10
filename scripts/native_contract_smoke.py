"""Offline end-to-end contract test across all eleven MrStore distribution targets.

Uses ONE synthetically approved, intentionally non-runnable image digest. It
tests packaging and parsers, never installs containers and cannot certify runtime.
Do not reuse sample manifests as production applications.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from zipfile import ZipFile

import yaml

try:
    from export_universal import export
    from export_portable_catalog import build as portable_build
    from export_homedock import build as homedock_build
    from export_olares_preview import package as olares_build, _name
    from export_umbrel_preview import package as umbrel_build
    from export_runtipi_preview import package as runtipi_build
    from platform_support_report import report
except ImportError:
    from scripts.export_universal import export
    from scripts.export_portable_catalog import build as portable_build
    from scripts.export_homedock import build as homedock_build
    from scripts.export_olares_preview import package as olares_build, _name
    from scripts.export_umbrel_preview import package as umbrel_build
    from scripts.export_runtipi_preview import package as runtipi_build
    from scripts.platform_support_report import report

# A deliberately fake registry digest: validated as syntax only, never pulled.
DUMMY_IMAGE = "docker.io/library/nginx@sha256:" + "a" * 64


def fixture(root: Path) -> tuple[Path, Path]:
    source = root / "release-source"
    app = source / "Apps" / "demo"
    app.mkdir(parents=True, exist_ok=False)
    doc = {
        "name": "mrstore-contract-demo",
        "services": {
            "web": {
                "image": DUMMY_IMAGE,
                "restart": "unless-stopped",
                "environment": {"TZ": "Europe/Lisbon"},
                "ports": [{"published": 18080, "target": 80, "protocol": "tcp"}],
                "volumes": [{"type": "bind", "source": "/DATA/AppData/demo/config",
                             "target": "/config"}],
            }
        },
        "x-casaos": {
            "id": "io.github.mrpiracy94.demo", "main": "web",
            "port_map": "18080", "scheme": "http", "version": "1.2.3",
            "architectures": ["amd64", "arm64"],
            "title": {"en_US": "MrStore Test"},
            "tagline": {"en_US": "Synthetic non-runnable adapter contract"},
            "category": "Utilities",
        },
    }
    (app / "docker-compose.yml").write_text(
        yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    for name in ("store-config.json", "supported-languages.json",
                 "category-list.json", "recommend-list.json"):
        (source / name).write_text("[]", encoding="utf-8")
    selection = root / "release-selection.json"
    selection.write_text(
        json.dumps({"approved": ["demo"], "approved_count": 1}),
        encoding="utf-8")
    return source, selection


def _cmd(arguments: list[str], cwd: Path | None = None) -> None:
    finished = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True,
                              timeout=45, check=False)
    if finished.returncode:
        raise RuntimeError(f"Parser {arguments!r} failed:\n{finished.stdout[-3000:]}\n"
                           f"{finished.stderr[-3000:]}")


def evaluate(output: Path, external: bool = False) -> dict:
    if output.exists():
        raise ValueError(f"Refusing to overwrite existing contract evidence: {output}")
    output.mkdir(parents=True)
    source, selection = fixture(output)
    dist = output / "dist"
    dist.mkdir()
    (dist / "store").mkdir()

    if export(source, selection, dist / "store/casaos-homeio-preview.zip") != 1:
        raise ValueError("CasaOS/Homeio export failed")
    portable_build(source, selection, dist)
    homedock_build(source, selection, dist / "homedock")
    olares_build(source, selection, dist / "olares")
    umbrel_build(source, selection, dist / "store/umbrel-community-preview.zip")
    runtipi_build(source, selection, dist / "store/runtipi-store-preview.zip")
    matrix = report(selection, dist)
    if len(matrix["systems"]) != 11:
        raise ValueError("Eleven system profiles were not generated")
    failed = [x["id"] for x in matrix["systems"] if x["format_eligible_count"] != 1]
    if failed:
        raise ValueError(f"Synthetic format gaps: {failed}")

    # Assert complete inner package composition, not just archive existence.
    expected = {
        "store/umbrel-community-preview.zip": {
            "umbrel-app-store.yml", "mrstore-demo/umbrel-app.yml",
            "mrstore-demo/docker-compose.yml"},
        "store/runtipi-store-preview.zip": {
            "apps/demo/config.json", "apps/demo/docker-compose.yml",
            "apps/demo/metadata/logo.jpg"},
        "homedock/mrstore.hdstore": {
            "store_manifest.json", "packages/demo.hds", ".hdstore_signature"},
        "olares/olares-oac-preview.zip": {
            _name("demo") + "/Chart.yaml",
            _name("demo") + "/OlaresManifest.yaml",
            _name("demo") + "/templates/workload.yaml"},
    }
    for location, required in expected.items():
        with ZipFile(dist / location) as archive:
            if archive.testzip() is not None or not required.issubset(archive.namelist()):
                raise ValueError("Missing/invalid archive entries: " + location)

    tools = {"docker_compose_config": False, "helm_lint": False, "helm_template": False}
    if external:
        if shutil.which("docker") is None or shutil.which("helm") is None:
            raise RuntimeError("Official Docker Compose V2 and Helm3 required for --external")
        _cmd(["docker", "compose", "-f",
              str(dist / "universal/compose/demo.yml"), "config", "--quiet"])
        tools["docker_compose_config"] = True
        chart = dist / "olares" / (_name("demo") + ".tgz")
        _cmd(["helm", "lint", str(chart), "--strict"])
        tools["helm_lint"] = True
        _cmd(["helm", "template", "mrstore-contract", str(chart),
              "--namespace", "default"])
        tools["helm_template"] = True

    result = {
        "schema": 1,
        "sample_only": True,
        "dummy_image_not_pulled": True,
        "format_contracts_tested": 11,
        "tested_platforms": [x["id"] for x in matrix["systems"]],
        "external_parsers": tools,
        "real_installations_tested": 0,
        "real_upgrades_tested": 0,
        "native_certified": False,
        "warning": "Synthetic structural CI is not native OS installation certification.",
    }
    (output / "native-format-evidence.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--external", action="store_true")
    opts = p.parse_args()
    print(json.dumps(evaluate(opts.output, opts.external), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
