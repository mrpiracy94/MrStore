"""Opt-in, read-only ZimaOS runtime smoke test for an already installed app.

No docker run/up/pull, no access to secrets, and no host URL in output.
An HTTP response proves reachability, not correct application behavior.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from catalog import apps


def container_snapshot(container_name: str) -> dict:
    completed = subprocess.run(
        ["docker", "inspect", "--type", "container", container_name],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Container not found or Docker inspect unavailable.")
    result = json.loads(completed.stdout)
    if not isinstance(result, list) or len(result) != 1:
        raise RuntimeError("Unexpected Docker inspect response.")
    item = result[0]
    # Never expose the full inspect payload; it contains environment variables.
    return {
        "running": item.get("State", {}).get("Running") is True,
        "published": item.get("NetworkSettings", {}).get("Ports") or {},
    }


def observed_port(snapshot: dict, published: str) -> bool:
    for mapping in snapshot.get("published", {}).values():
        if not isinstance(mapping, list):
            continue
        if any(isinstance(item, dict) and str(item.get("HostPort")) == published
               for item in mapping):
            return True
    return False


def http_probe(url: str, timeout: float) -> tuple[bool, int | None]:
    try:
        with urlopen(url, timeout=timeout) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, TimeoutError, OSError):
        return False, None
    # 401/403 indicate a live endpoint, not a successful login.
    return status in (200, 201, 202, 203, 204, 301, 302, 303, 307, 308, 401, 403), status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, help="Apps/ folder name")
    parser.add_argument("--host", required=True, help="NAS hostname or address (not stored)")
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--skip-http", action="store_true",
                        help="Only inspect container/port; never counts as HTTP-tested")
    args = parser.parse_args()
    app = next((a for a in apps() if a.folder == args.app), None)
    if app is None:
        parser.error("App folder not found")
    main_service = app.source["services"][app.metadata["main"]]
    container = main_service.get("container_name")
    if not isinstance(container, str):
        parser.error("This app has no fixed main container name")
    port = str(app.metadata["port_map"])
    scheme = app.metadata.get("scheme", "http")
    if any(x in args.host for x in ("/", "@", "?", "#", ":")):
        parser.error("--host must be a hostname/IP without URL scheme, port or credentials")
    if scheme not in ("http", "https"):
        parser.error("Unsupported scheme")
    outcome = {"app": app.folder, "check": "runtime_smoke_only",
               "container_running": False, "port_exposed": None,
               "http_reachable": None, "http_status": None,
               "full_app_functionality_verified": False}
    try:
        snapshot = container_snapshot(container)
        outcome["container_running"] = snapshot["running"]
        if port != "0":
            outcome["port_exposed"] = observed_port(snapshot, port)
            if outcome["container_running"] and outcome["port_exposed"] and not args.skip_http:
                index = app.metadata.get("index", "/")
                url = f"{scheme}://{args.host}:{port}{index}"
                ok, status = http_probe(url, args.timeout)
                outcome["http_reachable"] = ok
                outcome["http_status"] = status
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError):
        outcome["error"] = "Docker inspection failed; check local permissions/container status."
    outcome["smoke_pass"] = (
        outcome["container_running"]
        and outcome["port_exposed"] is True
        and outcome["http_reachable"] is True
    )
    print(json.dumps(outcome, indent=2, ensure_ascii=False))
    return 0 if outcome["smoke_pass"] or (port == "0" and outcome["container_running"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
