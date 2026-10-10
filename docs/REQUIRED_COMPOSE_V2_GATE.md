# Required Compose secrets: fail-closed ZimaOS v2 publication

MrStore must not publish an app that relies on required Docker Compose host
interpolation (`\${VAR:?message}` or `\${VAR?message}`) unless the
actual install environment is known to collect and provide that variable
**before** Compose parsing.

The official ZimaOS v2 builder
[build-appstore-action](https://github.com/IceWhaleTech/build-appstore-action/blob/main/scripts/build_appstore.py)
removes `services.*.x-casaos`, including `envs` descriptions, when
generating the distribution. Merely putting `x-casaos.envs` in a source
Compose file does not prove that the installer can prompt for credentials.

**Current policy:** the release selector quarantines any service with required
Compose interpolation. It reports an explicit reason in `release-status.json`
and continues publishing other independent apps that pass all CVE checks.
Source manifests and app data are untouched. Optional interpolations
(`\${VAR:-default}`) are not classified as mandatory by this rule;
other security checks still apply.

This is deliberately conservative. Do not remove the gate to get more green
checks or use public secret defaults. Upgrade it only after a documented,
working ZimaOS v2 installation mechanism securely injects host-side secrets,
with a real-device installation test. No NAS execution is implied by CI.
