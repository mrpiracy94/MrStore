# Security Policy — MrStore

Please report possible security flaws in the MrStore automation privately to the maintainer via GitHub Security Advisories when enabled. Avoid publishing exploitable secrets in public issues.

## Scope

- MrStore hosts Compose definitions. It does not run containers or expose a management API.
- The published catalog is community-maintained, not an endorsement or security guarantee for apps or images.
- All images should be evaluated before deployment, especially those with `privileged`, Docker socket access, `seccomp:unconfined`, host networking and placeholder credentials.
- Daily vulnerability scans use Trivy on a rotating 8-day schedule; CRITICAL results may open issues. A scanner failure must never be treated as a clean bill of health.
- Image digest monitoring detects changed published images, not necessarily new upstream releases. Renovate can propose semver tag updates if explicitly enabled.
- No automatic container updates, auto-merge or remote ZimaOS admin actions are performed.

## Verify before deployment

Open GitHub Actions to review the latest build, validation, CVE scan and Docker update reports. Verify downloaded images for the correct architecture and review the upstream repository's release notes.

## Mandatory secrets and Docker socket exceptions

Read [docs/SECURE_DEPLOYMENT.md](docs/SECURE_DEPLOYMENT.md) before deploying apps requiring credentials or host Docker access. `read_only` does **not** make a mounted Docker socket read-only at the API level. The Kasm image requires `privileged` upstream; do not install it on a shared or untrusted host.
