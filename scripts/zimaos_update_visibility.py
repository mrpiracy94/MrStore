"""Read-only visibility audit for ZimaOS app updates (especially ZimaOS 1.7.1).

Static analysis runs in CI. Optional --runtime probes an existing NAS without
pulling images, installing apps, restarting services, or writing Docker files.
Observations are not proof that the ZimaOS UI will offer an upgrade.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from catalog import ROOT, apps

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def is_latest(image: str) -> bool:
    """Detect the ZimaOS :latest comparison branch even for digest-pinned refs."""
    tagged = image.split("@", 1)[0].rsplit("/", 1)[-1]
    return tagged.endswith(":latest")


def catalog_item(app) -> dict:
    meta = app.metadata
    services = app.source.get("services") or {}
    main = meta.get("main")
    spec = services.get(main, {}) if isinstance(services, dict) else {}
    if not isinstance(spec, dict):
        spec = {}
    container = spec.get("container_name")
    image = spec.get("image")
    findings = []
    if not isinstance(main, str) or main not in services:
        findings.append("invalid_main_service")
    elif not isinstance(container, str) or not container:
        findings.append("main_container_name_not_explicit")
    elif container != main:
        findings.append("main_container_name_differs_from_service")
    if not isinstance(image, str) or not image:
        findings.append("missing_main_image")
    elif is_latest(image):
        findings.append("latest_requires_usable_local_repodigest")
    return {
        "app": app.folder, "app_id": app.app_id, "main_service": main,
        "main_container": container if isinstance(container, str) else None,
        "compose_project": app.source.get("name") or app.folder,
        "main_image": image if isinstance(image, str) else None,
        "findings": findings,
    }


def scan_catalog(root: Path) -> dict:
    entries = [catalog_item(app) for app in apps(root)]
    counter = Counter(code for entry in entries for code in entry["findings"])
    return {
        "catalog_apps": len(entries),
        "counts": dict(sorted(counter.items())),
        "apps": entries,
    }


def command(args: list[str], timeout: int = 20, runner=subprocess.run) -> tuple[str | None, str | None]:
    try:
        result = runner(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, "command_unavailable_or_timed_out"
    if result.returncode != 0:
        # Avoid leaking Docker config / registry credentials from stderr.
        return None, "command_failed"
    return result.stdout.strip(), None


def docker_names(runner=subprocess.run) -> tuple[set[str] | None, str | None]:
    value, error = command(["docker", "ps", "-a", "--format", "{{.Names}}"], runner=runner)
    return (set(value.splitlines()), None) if error is None else (None, error)


def docker_repo_digests(image: str, runner=subprocess.run) -> tuple[list[str] | None, str | None]:
    value, error = command(
        ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
        runner=runner,
    )
    if error:
        return None, error
    try:
        parsed = json.loads(value)
    except ValueError:
        return None, "invalid_docker_digests_json"
    if parsed is None:
        return [], None
    if not isinstance(parsed, list) or any(not isinstance(x, str) for x in parsed):
        return None, "invalid_docker_digests_json"
    return parsed, None


def installed_container_image(container: str, runner=subprocess.run) -> tuple[str | None, str | None]:
    # Only retrieve the configured image reference, never Config.Env or secret labels.
    value, error = command(
        ["docker", "container", "inspect", container, "--format", "{{.Config.Image}}"],
        runner=runner,
    )
    return (value, None) if value and not error else (None, error or "missing_installed_image")


def installed_container_image_id(container: str, runner=subprocess.run) -> tuple[str | None, str | None]:
    """Return the immutable image ID held by the container, not its mutable tag.

    A later `docker pull image:latest` can move that tag to a new image without
    changing the image running in the existing container.
    """
    value, error = command(
        ["docker", "container", "inspect", container, "--format", "{{.Image}}"],
        runner=runner,
    )
    if error:
        return None, error
    if not value or not SHA256.fullmatch(value):
        return None, "invalid_installed_image_id"
    return value, None


def registry_digest(image: str, runner=subprocess.run) -> tuple[str | None, str | None]:
    # Manifest inspection does not pull/install images. Must be explicitly requested.
    value, error = command(["crane", "digest", image], timeout=60, runner=runner)
    if error:
        return None, error
    return (value, None) if SHA256.fullmatch(value or "") else (None, "invalid_registry_digest")


def compare_digests(local: list[str] | None, remote: str | None) -> str:
    if local is None:
        return "unknown_local_inspection_failed"
    if not local:
        return "unknown_missing_repodigests"
    if remote is None:
        return "unknown_remote_not_checked"
    digests = {value.rsplit("@", 1)[-1] for value in local if "@sha256:" in value}
    if not digests:
        return "unknown_missing_usable_repodigest"
    return "digest_matches" if remote in digests else "digest_differs_review_required"


def validate_api_base(value: str) -> str:
    p = urlsplit(value)
    # Never issue authenticated/local admin API requests to arbitrary remote URLs.
    if p.scheme != "http" or p.hostname not in ("127.0.0.1", "localhost", "::1") or p.username or p.password:
        raise ValueError("App Management API must use loopback HTTP with no credentials")
    if p.path not in ("", "/") or p.query or p.fragment or p.port is None:
        raise ValueError("Supply only http://127.0.0.1:PORT")
    return value.rstrip("/")


def native_upgradable(api_base: str, app_id: str, folder: str, opener=urlopen) -> str:
    """Optional local API observation; an absent item is not proof of up-to-date."""
    target = validate_api_base(api_base) + "/v2/app_management/apps/upgradable"
    try:
        with opener(target, timeout=8) as response:
            payload = json.loads(response.read(2_000_000))
    except (OSError, TimeoutError, ValueError, HTTPError, URLError):
        return "unavailable_or_auth_required"
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(rows, dict):
        rows = rows.get("items") or rows.get("apps") or rows.get("list")
    if not isinstance(rows, list):
        return "unrecognized_response"
    for row in rows:
        if not isinstance(row, dict):
            continue
        if app_id in (row.get("id"), row.get("store_app_id")) or folder in (
                row.get("id"), row.get("store_app_id")):
            return "listed_as_upgradable"
    return "not_listed_not_proof_of_current"


def runtime_check(item: dict, *, check_registry: bool = False,
                  api_base: str | None = None, runner=subprocess.run, opener=urlopen) -> dict:
    """Inspect only one explicitly selected app; never modify the NAS."""
    outcome = {
        "app": item["app"], "expected_service": item["main_service"],
        "expected_container": item["main_container"],
        "main_image": item["main_image"],
        "zimaos_main_lookup_risk": "main_container_name_differs_from_service" in item["findings"]
                                 or "main_container_name_not_explicit" in item["findings"],
    }
    names, names_error = docker_names(runner)
    if names_error:
        outcome.update(installed="unknown", docker_error=names_error)
        return outcome
    expected = item["main_container"] or f"{item['compose_project']}-{item['main_service']}-1"
    actual = expected if expected in names else None
    outcome["installed"] = "found" if actual else "not_found_by_expected_name"
    outcome["expected_docker_name"] = expected
    outcome["zimaos_service_name_resolves"] = item["main_service"] in names
    if not actual:
        # Do not equate "not found by our expected name" with "not installed".
        outcome["update_evidence"] = "unknown_container_not_identified"
    else:
        local_ref, container_error = installed_container_image(actual, runner)
        if container_error:
            outcome["container_inspect_error"] = container_error
            outcome["update_evidence"] = "unknown_installed_image_unavailable"
        else:
            outcome["installed_image"] = local_ref
            image_id, id_error = installed_container_image_id(actual, runner)
            if id_error:
                # Never fall back to inspecting a mutable tag; it can refer to
                # an image which is NOT running in the selected container.
                local, error = None, id_error
            else:
                outcome["installed_image_id"] = image_id
                local, error = docker_repo_digests(image_id, runner)
            outcome["repodigests_present"] = bool(local) if local is not None else None
            if error:
                outcome["docker_image_error"] = error
            catalog_ref = item["main_image"]
            remote, remote_error = registry_digest(catalog_ref, runner) if (
                check_registry and catalog_ref) else (None, None)
            if remote_error:
                outcome["registry_error"] = remote_error
            outcome["update_evidence"] = compare_digests(local, remote)
            # Never expose Docker image inspect/config/env/credentials.
    if api_base is not None:
        outcome["native_update_api"] = native_upgradable(
            api_base, item["app_id"], item["app"], opener=opener)
    return outcome


def markdown(report: dict) -> str:
    catalog = report["catalog"]
    lines = [
        "# MrStore — ZimaOS update visibility audit", "",
        f"Apps reviewed: {catalog['catalog_apps']}", "",
        "This audit does not modify a NAS or guarantee the ZimaOS dashboard update badge.",
        "Catalog x-casaos.version and content_hash cannot by themselves repair "
        "native container update detection.", "",
    ]
    for code, count in catalog["counts"].items():
        lines.append(f"- {code}: **{count}**")
    lines += ["", "## Main-service compatibility risks", ""]
    risks = [item for item in catalog["apps"] if any(
        k in item["findings"] for k in
        ("main_container_name_not_explicit", "main_container_name_differs_from_service"))]
    for item in risks:
        lines.append(f"- {item['app']}: main `{item['main_service']}`, container `{item['main_container'] or 'Compose generated'}`")
    if not risks:
        lines.append("No main-service/container-name mismatch detected.")
    if report.get("runtime"):
        r = report["runtime"]
        lines += ["", "## Optional NAS read-only probe", "",
                  f"- app: {r['app']}",
                  f"- container identification: {r.get('installed', 'unknown')}",
                  f"- ZimaOS main-service lookup resolves: {r.get('zimaos_service_name_resolves', 'unknown')}",
                  f"- registry evidence: {r.get('update_evidence', 'unknown')}",
                  f"- native App Management verdict: {r.get('native_update_api', 'not_queried')}", ""]
    lines += ["", "Upstream bugs: https://github.com/IceWhaleTech/ZimaOS/issues/591 "
              "and https://github.com/IceWhaleTech/ZimaOS/issues/592.", ""]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--output", type=Path, default=ROOT / "out/zimaos-update-visibility.json")
    p.add_argument("--summary", type=Path, default=ROOT / "out/zimaos-update-visibility.md")
    p.add_argument("--runtime", action="store_true", help="Read-only Docker probe on this machine")
    p.add_argument("--app", help="Specific catalog folder (required for --runtime)")
    p.add_argument("--registry-check", action="store_true",
                   help="Read registry digest via crane without pulling any Docker image")
    p.add_argument("--api-base", help="Optional local App Management HTTP host, e.g. http://127.0.0.1:PORT")
    args = p.parse_args()
    if args.runtime and not args.app:
        p.error("--runtime requires --app so the probe does not inspect unrelated containers")
    if (args.registry_check or args.api_base) and not args.runtime:
        p.error("--registry-check and --api-base require --runtime")
    if args.api_base:
        try:
            validate_api_base(args.api_base)
        except ValueError as exc:
            p.error(str(exc))
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "scope": "static_only" if not args.runtime else "static_plus_selected_runtime",
              "catalog": scan_catalog(args.root)}
    if args.runtime:
        matches = [x for x in report["catalog"]["apps"] if x["app"] == args.app]
        if not matches:
            p.error("App not found in catalog")
        report["runtime"] = runtime_check(
            matches[0], check_registry=args.registry_check, api_base=args.api_base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.summary.write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    # Risks are reported, not treated as a pass/fail security gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
