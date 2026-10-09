# Security Policy — MrStore

Please report possible security flaws in the MrStore automation privately to the maintainer via GitHub Security Advisories when enabled. Avoid publishing exploitable secrets in public issues.

## Scope

- MrStore hosts Compose definitions. It does not run containers or expose a management API.
- The published catalog is community-maintained, not an endorsement or security guarantee for apps or images.
- All images should be evaluated before deployment, especially those with `privileged`, Docker socket access, `seccomp:unconfined`, host networking and placeholder credentials.
- Daily vulnerability scans use Trivy on all 8 image shards; HIGH/CRITICAL results open or update issues. A scanner failure must never be treated as a clean bill of health.
- Image digest monitoring detects changed published images, not necessarily new upstream releases. Renovate can propose semver tag updates if explicitly enabled.
- On catalog releases, every declared image architecture is scanned at an immutable digest; affected apps are excluded from the new build for any HIGH/CRITICAL findings, scan errors, or unsafe Compose privileges. All 8 reports are required. No publication is attempted if every app is quarantined. This does not revoke previously published catalogs.
- New Docker privilege escalation in PRs is blocked; existing settings require manual review before removal.
- No automatic container updates, auto-merge or remote ZimaOS admin actions are performed.

## Verify before deployment

Open GitHub Actions to review the latest build, validation, CVE scan and Docker update reports. Verify downloaded images for the correct architecture and review the upstream repository's release notes.
