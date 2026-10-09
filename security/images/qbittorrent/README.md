# Security-patched qBittorrent image

This is a temporary derived image for `qBittorrent 5.2.4` with the
`libtorrent v1` runtime, produced from the official LinuxServer.io image.

The build only upgrades packages from the image's existing Alpine repositories
(`apk upgrade --no-cache`). The resulting AMD64 and ARM64 images are individually
scanned using Trivy. Publishing **fails** if *any* HIGH or CRITICAL vulnerability
is found in either architecture; no CVEs are ignored.

Successful builds are tagged as:
`ghcr.io/mrpiracy94/mrstore-qbittorrent:5.2.4-libtorrentv1-secfix-20261009`.

Because this is a derived image, upstream updates do not apply automatically:
rebuild and re-scan whenever the base image or Alpine packages change.
The registry package must be **publicly readable** before the ZimaOS store can
reference it. The publication workflow does not modify live installations.

**Migration:** qBittorrent 4.6.7 -> 5.2.4 is a major upgrade. Back up
`/DATA/AppData/qbittorrent-4/config`, test on a non-production ZimaOS
installation, and plan an explicit rollback before changing the catalog entry.
