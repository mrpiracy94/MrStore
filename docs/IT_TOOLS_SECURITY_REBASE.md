# IT-Tools — targeted nginx Alpine security rebase

## What changed

The original image `corentinth/it-tools:latest` had 3 CRITICAL and 35 HIGH
findings in the MrStore Trivy audit. Switching between the upstream Docker Hub
and GHCR mirrors did not change those findings.

Instead, MrStore's `security/images/it-tools/Dockerfile`:

1. Fetches the original vendor image at a **fixed multi-platform digest**.
2. Copies only `/usr/share/nginx/html` (the already-built static app) and
   `/etc/nginx/conf.d/default.conf` (the vendor's nginx routes).
3. Serves the unchanged files using a newer, security-updated official
   `nginx:stable-alpine` runtime.

This is **not a change to IT-Tools' source or to other applications**.

## Verification

The workflow `release-patched-it-tools.yml` requires that:
- Both AMD64 and ARM64 images return **zero HIGH and zero CRITICAL CVEs**
  from a complete Trivy report.
- Every static web file and the nginx routing config are **byte-identical**
  to the corresponding vendor image for **each architecture**.
- Both images serve HTTP on port 80 in a disposable container.
- Only checked images are published to the MrStore GHCR container package.
- The actual ZimaOS manifest must use the published **immutable multiarch digest**,
  rather than a mutable tag.

The ZimaOS application remains `io.github.mrpiracy94.it-tools`, with its
original public port 30013, internal port 80 and **no persistent volumes**.

## Operational limits

- A clean scanner is not a guarantee of no exploitable vulnerabilities.
- The static app is from the pinned upstream release and will not automatically
  receive future upstream feature or bug fixes. New versions need repeat CI checks.
- If registry access fails, **do not point the catalog at an unavailable GHCR tag**.
- If a later security scan finds fresh vulnerabilities, leave the issue open
  and rebuild from a verified current runtime before release.

Original Dockerfile: https://github.com/CorentinTh/it-tools/blob/main/Dockerfile
