#!/usr/bin/env bash
set -euo pipefail
arch="${1:?amd64 or arm64}"
case "$arch" in amd64|arm64) ;; *) exit 2;; esac
image="mrstore-gitea-os-patch:${arch}"
name="mrstore-gitea-rootful-${arch}"
folder="$(mktemp -d)"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || :; sudo rm -rf "$folder"; }
trap cleanup EXIT

# Exact same rootful data layout, web port and SSH port as the existing manifest.
docker run -d --platform "linux/$arch" --name "$name" \
  -e USER_UID=1000 -e USER_GID=1000 -e TZ=Europe/Lisbon \
  -v "$folder:/data" \
  -p 127.0.0.1:13000:3000 -p 127.0.0.1:13001:22 \
  "$image" >/dev/null
for i in $(seq 1 100); do
  if curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:13000/; then
    sudo test -d "$folder/gitea"
    echo "PASS: $arch rootful Gitea web responds and /data/gitea persisted"
    exit 0
  fi
  if [[ "$(docker inspect --format '{{.State.Running}}' "$name")" != true ]]; then
    docker logs "$name" | tail -75
    exit 1
  fi
  sleep 2
done
docker logs "$name" | tail -75
exit 1
