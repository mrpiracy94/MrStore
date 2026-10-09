#!/usr/bin/env bash
# Disposable test; never attach production /DATA/AppData/healthchecks/config.
set -euo pipefail
arch="${1:?amd64|arm64}"
case "$arch" in amd64|arm64) ;; *) exit 2;; esac
name="mrstore-healthchecks-patch-${arch}"
work="$(mktemp -d)"
mkdir -p "$work/config"
touch "$work/config/existing-sentinel"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || :; sudo rm -rf "$work"; }
trap cleanup EXIT

docker run -d --platform "linux/$arch" --name "$name" \
  -p 127.0.0.1:28037:8000 \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Lisbon \
  -e SECRET_KEY=mrstore-testing-key-not-for-production-20261010 \
  -e SITE_ROOT=http://localhost:28037 \
  -e SUPERUSER_EMAIL=ci@example.test \
  -e SUPERUSER_PASSWORD=only-in-ci-temporary-password \
  -e ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e DEBUG=False \
  -v "$work/config:/config" \
  "mrstore-healthchecks-patched:$arch" >/dev/null

for i in $(seq 1 100); do
  code="$(curl -s -S -L --max-time 3 -o "$work/page.html" -w '%{http_code}' \
    http://127.0.0.1:28037/ 2>/dev/null || :)"
  if [[ "$code" == 200 ]] && grep -Eiq '(healthchecks|Log [Ii]n|[Ss]ign [Ii]n)' "$work/page.html"; then
    test -f "$work/config/existing-sentinel"
    docker exec "$name" /lsiopy/bin/python -c "import jwt, msgpack, setuptools, urllib3; \
assert jwt.__version__ == '2.14.0'; \
assert msgpack.version[0] >= 1; \
assert urllib3.__version__ == '2.8.0'"
    echo "PASS: $arch Healthchecks login HTML and existing /config with patched modules."
    exit 0
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$name")" != true ]]; then
    docker logs "$name" | tail -70
    echo "Healthchecks exited before readiness" >&2
    exit 1
  fi
  sleep 2
done
docker logs "$name" | tail -70
echo "Healthchecks not ready" >&2
exit 1
