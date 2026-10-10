"""Docker/Linux REAL runtime pilot; isolated CI, zero claims of C3/C4 certification."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import secrets
import socket
import subprocess
import time
from urllib.request import build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import yaml

APP = "it-tools"
APP_ID = "io.github.mrpiracy94.it-tools"
DIGEST = re.compile(r"^[A-Za-z0-9./:_-]+@sha256:[a-f0-9]{64}$")


def validate_release(manifest: Path, selection: Path, catalog: Path):
    approved = json.loads(selection.read_text(encoding="utf-8"))
    apps = approved.get("approved", [])
    if not isinstance(apps, list) or approved.get("approved_count") != len(apps) or len(set(apps)) != len(apps):
        raise ValueError("Invalid security-approved release")
    if APP not in apps:
        return None
    if not manifest.is_file() or not catalog.is_file():
        raise ValueError("Approved Compose or catalog absent")
    release = json.loads(catalog.read_text(encoding="utf-8"))
    if release.get("approved_count") != len(apps) or not any(
        isinstance(x, dict) and x.get("slug") == APP and x.get("id") == APP_ID
        for x in release.get("apps", [])
    ):
        raise ValueError("Approved app set and catalog inconsistent")
    doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or set(doc) - {"name", "services", "x-casaos"}:
        raise ValueError("Unexpected top-level Compose directives")
    metadata = doc.get("x-casaos")
    if not isinstance(metadata, dict) or metadata.get("id") != APP_ID or metadata.get("main") != APP:
        raise ValueError("App identity/main service mismatch")
    if "amd64" not in metadata.get("architectures", []):
        raise ValueError("Not approved for runner architecture")
    services = doc.get("services")
    if not isinstance(services, dict) or set(services) != {APP}:
        raise ValueError("Not the expected single-service static app")
    service = services[APP]
    allowed = {"image", "container_name", "restart", "ports", "x-casaos"}
    if not isinstance(service, dict) or set(service) - allowed:
        raise ValueError("Unexpected volumes, secrets or privileged settings")
    image = service.get("image")
    if not isinstance(image, str) or not DIGEST.fullmatch(image):
        raise ValueError("Image must be immutable and digest-pinned")
    ports = service.get("ports")
    if not isinstance(ports, list) or len(ports) != 1 or not isinstance(ports[0], dict) or str(ports[0].get("target")) != "80" or ports[0].get("protocol", "tcp") != "tcp":
        raise ValueError("Unexpected HTTP port")
    return {"image": image, "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}


def bounded_compose(approved, port):
    return {"services": {APP: {
        "image": approved["image"],
        "restart": "no",
        "ports": [{"target": 80, "published": str(port), "host_ip": "127.0.0.1", "protocol": "tcp"}],
        "pids_limit": 128,
        "mem_limit": "512m",
        "security_opt": ["no-new-privileges:true"],
        "cap_drop": ["NET_RAW", "MKNOD", "AUDIT_WRITE", "SETFCAP"],
    }}}


def cmd(args, timeout=120, strict=True):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if strict and r.returncode:
        raise RuntimeError("Docker command failed, exit code: " + str(r.returncode))
    return r.stdout.strip()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def reachable(port, timeout=65):
    opener = build_opener(NoRedirect())
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with opener.open(f"http://127.0.0.1:{port}/", timeout=3) as r:
                body = r.read(128000).decode("utf-8", errors="replace")
                if r.status == 200 and "it-tools" in body.lower():
                    return True
        except (HTTPError, URLError, TimeoutError, OSError):
            pass
        time.sleep(1.5)
    return False


def pilot(manifest, selection, catalog, output):
    if output.exists():
        raise ValueError("Cannot overwrite existing runtime evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema": 1, "app": APP, "platform": "docker-linux",
        "method": "ephemeral_gitHub_hosted_ubuntu_docker_compose",
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "amd64",
        "status": "not_executed", "live_container_executed": False,
        "http_verified": False, "restart_http_verified": False,
        "c2_candidate": False, "c3_verified": False, "c4_verified": False,
        "native_certified": False, "no_data_persistence_or_upgrade_tests": True,
    }
    working = output.parent / ("mrstore-pilot-" + secrets.token_hex(5) + ".yml")
    project = "mrstorecert" + secrets.token_hex(5)
    attempted = False
    try:
        approved = validate_release(manifest, selection, catalog)
        if approved is None:
            evidence["status"] = "skipped_not_approved_by_trivy"
            return evidence
        if platform.machine().lower() not in ("x86_64", "amd64"):
            raise ValueError("Pilot supports amd64 only")
        evidence.update({"image": approved["image"], "audited_compose_sha256": approved["sha256"]})
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        working.write_text(yaml.safe_dump(bounded_compose(approved, port)), encoding="utf-8")
        cmd(["docker", "compose", "-f", str(working), "config", "--quiet"], timeout=30)
        cmd(["docker", "pull", approved["image"]], timeout=180)
        evidence["docker_version"] = cmd(["docker", "version", "--format", "{{.Server.Version}}"], timeout=15)
        evidence["compose_version"] = cmd(["docker", "compose", "version", "--short"], timeout=15)
        attempted = True
        cmd(["docker", "compose", "-p", project, "-f", str(working), "up", "-d", "--pull", "never", "--no-build"], timeout=90)
        cid = cmd(["docker", "compose", "-p", project, "-f", str(working), "ps", "-q", APP], timeout=20)
        if not cid or "\n" in cid or cmd(["docker", "inspect", "-f", "{{.State.Running}}", cid], timeout=20) != "true":
            raise RuntimeError("Docker container is not running")
        if not reachable(port):
            raise RuntimeError("HTTP application not ready")
        evidence["live_container_executed"] = True
        evidence["http_verified"] = True
        cmd(["docker", "compose", "-p", project, "-f", str(working), "restart", APP], timeout=50)
        if not reachable(port):
            raise RuntimeError("HTTP did not recover after container restart")
        evidence["restart_http_verified"] = True
        evidence["c2_candidate"] = True
        evidence["status"] = "live_http_restart_passed_review_required"
        return evidence
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        evidence["status"] = "failed"
        evidence["reason"] = type(exc).__name__
        raise
    finally:
        if attempted:
            cmd(["docker", "compose", "-p", project, "-f", str(working), "down", "--volumes", "--remove-orphans"], timeout=60, strict=False)
        working.unlink(missing_ok=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--selection", type=Path, required=True)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    data = pilot(args.manifest, args.selection, args.catalog, args.output)
    print(f"Live Docker pilot: {data['status']} (C4 certified: false)")


if __name__ == "__main__":
    main()
