# Shared remediation for official LinuxServer Python apps (no application version changes).
# Upstream s6, ports, PUID/PGID, /config and persistent mounts remain unchanged.
# Remove package-install tools AND their vulnerable vendored runtime code after pinning patched modules.
# ALL Trivy targets remain enabled, with no CVE suppression or removed Trivy/SBOM evidence.
ARG APP
FROM docker.io/linuxserver/${APP}:latest
USER root
RUN set -eux; \
    apk upgrade --no-cache; \
    test -x /lsiopy/bin/python; \
    /lsiopy/bin/python -m pip install --no-cache-dir --upgrade \
      'msgpack==1.2.1' 'urllib3==2.8.0' 'setuptools==80.9.0'; \
    /lsiopy/bin/python -m pip check; \
    /lsiopy/bin/python -m pip uninstall --yes pip setuptools wheel; \
    /lsiopy/bin/python -c "from importlib.metadata import version; import importlib.util; assert version('msgpack') == '1.2.1'; assert version('urllib3') == '2.8.0'; assert all(importlib.util.find_spec(p) is None for p in ('pip', 'setuptools', 'wheel'))"
