# Preserve the complete LinuxServer Healthchecks image, s6, /config and port 8000.
# Official Docker Hub LinuxServer mirror avoids lscr.io registry 429 in CI.
# The last vulnerability evidence showed ten findings in exactly these packages.
FROM docker.io/linuxserver/healthchecks:latest
USER root
RUN test -x /lsiopy/bin/python \
 && /lsiopy/bin/python -m pip install --no-cache-dir --upgrade \
      'PyJWT==2.14.0' \
      'msgpack==1.2.1' \
      'setuptools==80.9.0' \
      'urllib3==2.8.0' \
 && /lsiopy/bin/python -m pip check \
 && /lsiopy/bin/python -m pip uninstall --yes pip setuptools wheel
# Removed from runtime: pip, setuptools and wheel, including vendored code.
# No Trivy ignores, skip-files, SBOM edits or CVE filtering.
