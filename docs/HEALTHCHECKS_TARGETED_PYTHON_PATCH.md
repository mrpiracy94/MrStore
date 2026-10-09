# Healthchecks — targeted Python security image

This remediates only the existing LinuxServer Healthchecks image, preserving the
s6 init system, `/config` data mapping, PUID/PGID and internal port 8000.
It **does not migrate** SQLite databases or replace Healthchecks itself.

## Security changes

The original LinuxServer image reports 1 CRITICAL and 9 HIGH vulnerabilities,
including `PyJWT 2.13.0`, `msgpack 1.1.2`, `setuptools 70.3.0` and
`urllib3 2.7.0`.

The Dockerfile installs patched Python runtime packages in `/lsiopy`, then
**physically uninstalls pip, setuptools and wheel from the final runtime image**.
Pip packages actual independent, older vulnerable vendored libraries and
CycloneDX metadata. Removing build/install tooling removes the vulnerable code
rather than manipulating Trivy's evidence or suppressing its detection.
We preserve full Trivy scans for both architectures (no ignored CVEs).

## Compatibility trade-off

The Healthchecks web server does not need Python package installation tools at
runtime. **Users running custom Docker mods or manually using
`/lsiopy/bin/python -m pip install` inside a running container may be affected**.
Do not migrate such installations without identifying those dependencies and
adapting them. This is a targeted and documented incompatibility, not an
automatic upgrade for every environment.

Run dualarch Trivy and actual login UI smoke tests against ephemeral data before
release. Retain the original persistent directory:

- `/DATA/AppData/healthchecks/config` → `/config`
- Port externally `20037` → internal `8000`

Before upgrading a real ZimaOS installation, stop the container, back up
`/DATA/AppData/healthchecks/config` and test that existing alerts, schedules,
ping URLs, secret keys and login work after restart. Never reset the database.

Upstream: https://docs.linuxserver.io/images/docker-healthchecks/
Pip vendoring and CVE metadata: https://github.com/aquasecurity/trivy/discussions/11031
