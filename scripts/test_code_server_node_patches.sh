#!/usr/bin/env bash
# Uses disposable volumes; never touches a real ZimaOS installation.
set -euo pipefail
arch="${1:?amd64 or arm64}"
case "$arch" in amd64|arm64) ;; *) exit 2;; esac
container="mrstore-codeserver-${arch}"
work="$(mktemp -d)"
mkdir -p "$work/config" "$work/workspace"
touch "$work/config/existing-settings-sentinel"
touch "$work/workspace/existing-project-sentinel"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; sudo rm -rf "$work"; }
trap cleanup EXIT
docker run -d --platform "linux/$arch" --name "$container" \
  -p 127.0.0.1:28443:8443 \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Lisbon \
  -e DEFAULT_WORKSPACE=/workspace \
  -v "$work/config:/config" -v "$work/workspace:/workspace" \
  "mrstore-code-server-patched:${arch}" >/dev/null
for i in $(seq 1 100); do
  status="$(curl --silent --show-error --max-time 3 --output /dev/null --write-out '%{http_code}' http://127.0.0.1:28443/ 2>/dev/null || :)"
  if [[ "$status" =~ ^[1-4][0-9][0-9]$ ]]; then
    test -f "$work/config/existing-settings-sentinel"
    test -f "$work/workspace/existing-project-sentinel"
    docker exec "$container" sh -c "grep -q '\"version\": \"1.11.0\"' /app/code-server/lib/vscode/node_modules/shell-quote/package.json"
    docker exec "$container" sh -c "grep -q '\"version\": \"6.2.1\"' /app/code-server/node_modules/basic-ftp/package.json"
    echo "PASS: $arch code-server HTTP and existing volumes with the patched modules."
    exit 0
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$container")" != true ]]; then
    docker logs "$container" | tail -60
    exit 1
  fi
  sleep 2
done
docker logs "$container" | tail -60
exit 1
