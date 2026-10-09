# MrStore rebuilt — implementation notes (2026-10-09)

The automated scripts, workflows and regression tests were developed anew. All 254 supplied app definitions are carried over as the source catalog; the runtime source is never executed for validation. The correct ZimaOS v2 builder is retained because it defines the official metadata conversion and content hash protocol.

**GitHub Actions builder evidence:** the first historic build published 155 and failed 99 (87 invalid icons + 12 ARM64 mismatches). After repairing them, the second historic build generated 229 entries and failed 25 further ARM64 mismatches. Those 25 are now marked amd64-only in the rebuilt source; none of those apps was silently discarded. A future clean CI build must still be observed before asserting all 254 were successfully published.

**Risks still pending:** external registries could refuse access or change their manifests, old third-party images could disappear, some apps are not designed for modern ZimaOS, icon placeholders are not upstream assets, and `1.0.0` represents MrStore's manifest revision rather than upstream release versions. CVE findings require a live Trivy scan. Some UI-less apps have a dummy port map; test on an actual ZimaOS client.

**Never auto-upgrade installed apps:** image digest changes lead to reports and issues, not deployments. Enable Renovate manually for pull-request-only tag upgrades; validate builds and review security implications.
