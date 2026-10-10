"""Block new Docker privilege escalation without breaking existing installations.

Compares risky service settings to the base Git revision. Legacy findings are
visible in the static audit but are not silently removed or normalized.
"""
import argparse
import json
import posixpath
from pathlib import Path
import subprocess
import yaml

from catalog import ROOT, apps


SENSITIVE_MOUNTS = frozenset({
    "/", "/etc", "/root", "/proc", "/sys", "/dev",
    "/var/run/docker.sock", "/run/docker.sock",
    "/run/containerd/containerd.sock", "/var/lib/docker", "/var/lib/containerd",
    "/etc/shadow", "/etc/gshadow", "/etc/sudoers", "/etc/ssh", "/etc/docker",
})


def sensitive_host_bind(source):
    """Detect mounted sensitive objects, ancestors and canonical path aliases.

    A bind of /var/run or /var can expose docker.sock even when its name is
    absent from Compose. Descendants of private runtime dirs are sensitive
    too; /etc/localtime and ordinary /DATA volumes remain allowed.
    """
    if not isinstance(source, str) or not source.startswith("/"):
        return False
    normalized = "/" + posixpath.normpath(source).lstrip("/")
    if normalized == "/":
        return True
    if normalized.endswith(("/docker.sock", "/containerd.sock")):
        return True
    if any(normalized == path or path.startswith(normalized.rstrip("/") + "/")
           for path in SENSITIVE_MOUNTS):
        return True
    private_subtrees = (
        "/root", "/proc", "/sys", "/dev",
        "/var/lib/docker", "/var/lib/containerd",
        "/etc/ssh", "/etc/docker",
    )
    return any(normalized.startswith(path + "/") for path in private_subtrees)



def risky_settings(doc):
    findings = set()
    services = doc.get("services") or {}
    if not isinstance(services, dict):
        raise ValueError("Malformed Compose services")
    for service, spec in services.items():
        if not isinstance(spec, dict):
            raise ValueError(f"Malformed service: {service}")
        prefix = str(service)
        for flag in ("privileged",):
            if spec.get(flag) is True:
                findings.add((prefix, flag, "true"))
        for flag in ("network_mode", "pid", "ipc", "uts"):
            if spec.get(flag) == "host":
                findings.add((prefix, flag, "host"))
        if str(spec.get("user", "")).lower().split(":", 1)[0] in ("root", "0"):
            findings.add((prefix, "user", "root"))
        capabilities = spec.get("cap_add") or []
        for cap in (capabilities if isinstance(capabilities, list) else [capabilities]):
            findings.add((prefix, "cap_add", str(cap)))
        options = spec.get("security_opt") or []
        for opt in (options if isinstance(options, list) else [options]):
            opt = str(opt).lower()
            if ("seccomp:unconfined" in opt or "seccomp=unconfined" in opt or
                    "apparmor:unconfined" in opt or "apparmor=unconfined" in opt or
                    opt in ("no-new-privileges:false", "no-new-privileges=false")):
                findings.add((prefix, "security_opt", opt))
        for mount in spec.get("volumes") or []:
            if isinstance(mount, dict):
                source = mount.get("source") if mount.get("type", "bind") == "bind" else None
            else:
                source = str(mount).split(":", 1)[0]
            if sensitive_host_bind(source):
                findings.add((prefix, "sensitive_mount", str(source)))
        for device in spec.get("devices") or []:
            findings.add((prefix, "device", json.dumps(device, sort_keys=True)))
    return findings


def manifests_at_revision(revision):
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", revision, "--", "Apps"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    result = {}
    for path in proc.stdout.splitlines():
        if not path.startswith("Apps/") or not path.endswith("/docker-compose.yml"):
            continue
        data = subprocess.run(["git", "show", f"{revision}:{path}"],
                              cwd=ROOT, capture_output=True, text=True, check=True)
        manifest = yaml.safe_load(data.stdout)
        if not isinstance(manifest, dict):
            raise ValueError(f"Invalid baseline manifest: {path}")
        result[Path(path).parent.name] = risky_settings(manifest)
    return result


def regressions(current, baseline):
    new = []
    for app in current:
        old = baseline.get(app.folder, set())
        for service, code, detail in sorted(risky_settings(app.source) - old):
            new.append(f"{app.folder}/{service}: new {code}={detail}")
    return new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Git commit to compare against")
    args = parser.parse_args()
    new = regressions(apps(), manifests_at_revision(args.base))
    if new:
        print("New privileged Docker configurations are not permitted:\n" +
              "\n".join(f"- {x}" for x in new))
        return 1
    print("Privilege policy: no new risky service permissions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
