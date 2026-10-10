"""Read-only ZimaOS image-update check using OCI config digests.

Compare the *running/created container's real local image ID* with the remote
OCI manifest's platform-specific config digest, even if RepoDigests == [].
This does not use the ZimaOS native update API, change Docker, or install apps.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
PLATFORM = re.compile(r"^linux/(amd64|arm64|arm)(?:/(?:v[0-9]+))?$")
MANIFEST_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}


def run(argv: list[str], *, runner=subprocess.run, timeout: int = 30) -> str:
    """Only call read commands; never expose Docker inspect JSON/environment."""
    try:
        proc = runner(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("unavailable_or_timed_out") from exc
    if proc.returncode:
        # Registry errors may include authorization headers; do not repeat stderr.
        raise RuntimeError("command_failed")
    return proc.stdout.strip()


def canonical_repository(reference: str) -> str:
    """Normalize Docker Hub shorthand without changing registries or tags."""
    if not reference or reference.startswith("sha256:"):
        raise ValueError("image_reference_missing_or_local_only")
    text = reference.split("@", 1)[0]
    last = text.rsplit("/", 1)[-1]
    if ":" in last:
        text = text.rsplit(":", 1)[0]
    if not text or text.startswith("/") or "//" in text or " " in text:
        raise ValueError("invalid_image_reference")
    parts = text.split("/")
    first = parts[0]
    if "." in first or ":" in first or first == "localhost":
        return text.lower()
    if len(parts) == 1:
        return "docker.io/library/" + text.lower()
    return "docker.io/" + text.lower()


def inspect_local(container: str, *, runner=subprocess.run) -> tuple[str, str, str]:
    if not container or container.startswith("-") or any(x.isspace() for x in container):
        raise ValueError("invalid_container_name")
    local_id = run(
        ["docker", "container", "inspect", container, "--format", "{{.Image}}"],
        runner=runner,
    )
    if not DIGEST.fullmatch(local_id):
        raise ValueError("invalid_installed_image_id")
    installed_ref = run(
        ["docker", "container", "inspect", container, "--format", "{{.Config.Image}}"],
        runner=runner,
    )
    platform = run(
        ["docker", "image", "inspect", local_id, "--format",
         "{{.Os}}/{{.Architecture}}{{if .Variant}}/{{.Variant}}{{end}}"],
        runner=runner,
    )
    if not PLATFORM.fullmatch(platform):
        raise ValueError("unsupported_or_ambiguous_platform")
    return local_id, installed_ref, platform


def remote_config_digest(reference: str, platform: str, *, runner=subprocess.run) -> str:
    if not PLATFORM.fullmatch(platform):
        raise ValueError("unsupported_or_ambiguous_platform")
    raw = run(["crane", "manifest", "--platform", platform, reference],
              runner=runner, timeout=70)
    try:
        manifest = json.loads(raw)
    except ValueError as exc:
        raise ValueError("registry_manifest_not_json") from exc
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 2:
        raise ValueError("invalid_registry_manifest")
    if manifest.get("mediaType") not in MANIFEST_TYPES:
        raise ValueError("unsupported_registry_manifest_type")
    config = manifest.get("config")
    digest = config.get("digest") if isinstance(config, dict) else None
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ValueError("invalid_registry_config_digest")
    return digest


def check(container: str, target: str | None = None, *, runner=subprocess.run) -> dict:
    result = {
        "container": container,
        "status": "unknown",
        "reason": None,
        "local_image_id": None,
        "installed_image_reference": None,
        "target_reference": target,
        "platform": None,
        "remote_config_digest": None,
        "zimaos_native_badge_verified": False,
        "updated_or_pulled": False,
    }
    try:
        image_id, installed_ref, platform = inspect_local(container, runner=runner)
        result.update(local_image_id=image_id, installed_image_reference=installed_ref,
                      platform=platform)
        if target is None and "@sha256:" in installed_ref:
            result.update(status="unknown", reason="immutable_reference_no_floating_target")
            return result
        reference = target or installed_ref
        local_repo = canonical_repository(installed_ref)
        remote_repo = canonical_repository(reference)
        if local_repo != remote_repo:
            result.update(reason="installed_and_target_repositories_differ")
            return result
        result["target_reference"] = reference
        remote_id = remote_config_digest(reference, platform, runner=runner)
        result["remote_config_digest"] = remote_id
        result["status"] = "candidate_update" if image_id != remote_id else "same_image"
        result["reason"] = (
            "remote_platform_image_config_differs_from_installed"
            if image_id != remote_id else "remote_platform_image_config_matches_installed"
        )
        return result
    except (ValueError, RuntimeError) as exc:
        result["reason"] = str(exc)
        return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--container", required=True, help="Installed Docker container name")
    p.add_argument("--target", help="Optional approved replacement tag or pinned digest, same repository")
    p.add_argument("--output", type=Path, help="Optional local JSON output; no Docker secrets included")
    args = p.parse_args(argv)
    result = check(args.container, args.target)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    print(data, end="")
    return 0 if result["status"] != "unknown" else 2


if __name__ == "__main__":
    sys.exit(main())
