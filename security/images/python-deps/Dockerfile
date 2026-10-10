# Targeted Python vulnerability remediation for five LinuxServer applications.
# Do not change application releases, init processes, service ports or volumes.
# Every resulting image must pass unsuppressed Trivy on AMD64 and ARM64.
ARG APP
FROM lscr.io/linuxserver/${APP}:latest
USER root
RUN set -eux; \
    apk upgrade --no-cache; \
    test -x /lsiopy/bin/python; \
    /lsiopy/bin/python -m pip install --no-cache-dir --upgrade \
      'msgpack==1.2.1' 'urllib3==2.8.0' 'setuptools==80.9.0'; \
    /lsiopy/bin/python -m pip check; \
    /lsiopy/bin/python -c "import msgpack, urllib3, setuptools; from importlib.metadata import version; assert version('msgpack') == '1.2.1'; assert version('urllib3') == '2.8.0'; assert version('setuptools') == '80.9.0'"
