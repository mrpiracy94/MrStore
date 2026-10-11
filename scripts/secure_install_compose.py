#!/usr/bin/env python3
"""Generate a private, per-install Docker Compose with strong unique credentials.

Works for ANY MrStore Compose that uses recognized CHANGE_ME placeholders.
No credentials are committed, uploaded or logged. Not an automatic ZimaOS prompt.
External service credentials/hosts are prompted, never invented.
"""
from __future__ import annotations

import argparse
import base64
import copy
import getpass
import os
from pathlib import Path
import re
import secrets
import sys

import yaml
from catalog import ROOT, APP_ID

PLACEHOLDER = re.compile(r"^CHANGE_ME(?:_[A-Z0-9_]+)?$")
SENSITIVE = re.compile(r"(?:PASS|TOKEN|SECRET|_KEY|APP_KEY|SEED)", re.I)
EXTERNAL_KEYS = {
    "bookstack": {"DB_HOST", "DB_PASSWORD"},
    "cloudflared": {"TUNNEL_TOKEN"},
    "frigate": {"FRIGATE_RTSP_PASSWORD"},
    "healthchecks": {"SUPERUSER_EMAIL"},
    "hedgedoc": {"DB_HOST", "DB_PASS", "CMD_DOMAIN"},
    "netbox": {"SUPERUSER_EMAIL", "DB_PASSWORD", "DB_HOST", "REDIS_HOST"},
}
SPECIAL_LINKED = {"immich": {"DB_PASSWORD": "immich_db", "POSTGRES_PASSWORD": "immich_db"}}


class NeedsConfiguration(ValueError):
    pass


def _secrets_group(app: str, key: str) -> str:
    return SPECIAL_LINKED.get(app, {}).get(key, key)


def resolve_manifest(source: dict, app: str, provided: dict | None = None,
                     password_factory=None) -> tuple[dict, list[str]]:
    """Return fully configured copy; fail if ANY runtime placeholder remains."""
    data = copy.deepcopy(source)
    services = data.get("services")
    if not isinstance(services, dict) or not services:
        raise NeedsConfiguration("Compose must contain services")
    provided = provided or {}
    factory = password_factory or (lambda: secrets.token_urlsafe(40))
    generated = {}
    keys_changed = []
    for service, spec in services.items():
        if not isinstance(spec, dict):
            raise NeedsConfiguration(f"Invalid service: {service}")
        env = spec.get("environment") or []
        if isinstance(env, list):
            pairs = [item.split("=", 1) if isinstance(item, str) and "=" in item else None
                     for item in env]
        elif isinstance(env, dict):
            pairs = [[str(k), v] for k, v in env.items()]
        else:
            raise NeedsConfiguration(f"Unsupported environment for {service}")
        for index, item in enumerate(pairs):
            if item is None:
                continue
            key, old = item
            if not isinstance(old, str) or not PLACEHOLDER.fullmatch(old):
                continue
            group = _secrets_group(app, key)
            if key in provided:
                new_value = provided[key]
                if not isinstance(new_value, str) or not new_value or PLACEHOLDER.fullmatch(new_value):
                    raise NeedsConfiguration(f"Invalid supplied value for {key}")
                if group in generated and generated[group] != new_value:
                    raise NeedsConfiguration(f"Inconsistent linked credential group for {key}")
                generated[group] = new_value
            elif group in generated:
                new_value = generated[group]
            elif key in EXTERNAL_KEYS.get(app, set()) or not SENSITIVE.search(key):
                raise NeedsConfiguration(
                    f"{app}: {key} requires real external configuration before installation")
            else:
                if key == "APP_KEY" and app == "bookstack":
                    generated[group] = "base64:" + base64.b64encode(
                        secrets.token_bytes(32)).decode("ascii")
                else:
                    generated[group] = factory()
                new_value = generated[group]
            pairs[index][1] = new_value
            keys_changed.append(key)
        if isinstance(env, list):
            spec["environment"] = [
                f"{pair[0]}={pair[1]}" if pair is not None else original
                for pair, original in zip(pairs, env)
            ]
        elif isinstance(env, dict):
            spec["environment"] = dict(pairs)
    # Inspect actual runtime fields, never descriptive x-casaos metadata.
    for service, spec in services.items():
        runtime = {k: v for k, v in spec.items() if not str(k).startswith("x-")}
        def check(value):
            if isinstance(value, str) and (
                PLACEHOLDER.fullmatch(value) or
                any(PLACEHOLDER.fullmatch(part) for part in value.split("=", 1)[1:])
            ):
                raise NeedsConfiguration(f"{app}/{service}: unconfigured runtime placeholder")
            if isinstance(value, dict):
                for v in value.values():
                    check(v)
            if isinstance(value, list):
                for v in value:
                    check(v)
        check(runtime)
    return data, sorted(set(keys_changed))


def prepare_from_repo(app: str, output: Path, provided: dict | None = None,
                      root: Path = ROOT, password_factory=None) -> list[str]:
    if not APP_ID.fullmatch(app) or "/" in app:
        raise NeedsConfiguration("Invalid app slug")
    source = (root / "Apps" / app / "docker-compose.yml").resolve()
    if not source.is_relative_to((root / "Apps").resolve()) or not source.is_file():
        raise NeedsConfiguration("App manifest not found")
    dest = output.resolve()
    if dest.is_relative_to(root.resolve()):
        raise NeedsConfiguration("Never write generated credentials inside the Git repository")
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise NeedsConfiguration("Invalid Compose")
    ready, keys = resolve_manifest(document, app, provided, password_factory)
    serialized = yaml.safe_dump(ready, allow_unicode=True, sort_keys=False)
    # O_EXCL refuses existing paths and symlinks; 0600 protects generated secrets.
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(serialized)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return keys


def external_questions(app: str, document: dict) -> list[str]:
    wanted = EXTERNAL_KEYS.get(app, set())
    observed = set()
    for spec in (document.get("services") or {}).values():
        env = spec.get("environment") or []
        pairs = env.items() if isinstance(env, dict) else (
            item.split("=", 1) for item in env if isinstance(item, str) and "=" in item)
        for name, value in pairs:
            if name in wanted and isinstance(value, str) and PLACEHOLDER.fullmatch(value):
                observed.add(name)
    return sorted(observed)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, help="App folder under Apps")
    parser.add_argument("--output", required=True, type=Path,
                        help="Write outside the Git repo, never overwrite")
    opts = parser.parse_args(argv)
    try:
        if not APP_ID.fullmatch(opts.app):
            raise NeedsConfiguration("Invalid app slug")
        path = ROOT / "Apps" / opts.app / "docker-compose.yml"
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        values = {}
        required = external_questions(opts.app, doc)
        if required and not sys.stdin.isatty():
            raise NeedsConfiguration("External values required; run interactively in a trusted terminal")
        for key in required:
            prompt = f"{opts.app}: set a REAL value for {key}: "
            value = (getpass.getpass(prompt) if SENSITIVE.search(key)
                     else input(prompt))
            if not value or PLACEHOLDER.fullmatch(value):
                raise NeedsConfiguration(f"{key} must be configured")
            values[key] = value
        keys = prepare_from_repo(opts.app, opts.output, values)
    except (NeedsConfiguration, OSError, ValueError, yaml.YAMLError) as exc:
        print("SECURE INSTALL BLOCKED:", exc, file=sys.stderr)
        return 2
    print(f"Private Compose created: {opts.output}. "
          f"{len(keys)} environment names configured. Secret values NOT displayed.")
    print("Check URLs, ports, accounts and backups; this is not a runtime certification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
