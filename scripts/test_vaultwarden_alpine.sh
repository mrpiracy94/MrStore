#!/usr/bin/env bash
# All volumes are disposable test fixtures, never users' real Vaultwarden data.
set -euo pipefail
container="mrstore-vaultwarden-compat"
work_dir="$(mktemp -d)"
data_dir="$work_dir/data"
base_url="http://127.0.0.1:17883"
mkdir -p "$data_dir"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  sudo rm -rf "$work_dir"
}
trap cleanup EXIT

ready() {
  for n in $(seq 1 100); do
    if curl -fsS "$base_url/alive" >/dev/null 2>&1; then return 0; fi
    if ! docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null | grep -q true; then
      echo "Vaultwarden exited before serving /alive" >&2
      docker logs "$container" 2>&1 | tail -35
      return 1
    fi
    sleep 2
  done
  echo "Vaultwarden not ready" >&2
  docker logs "$container" 2>&1 | tail -35
  return 1
}

start_image() {
  docker run -d --name "$container" \
    -p 127.0.0.1:17883:80 \
    -e SIGNUPS_ALLOWED=false \
    -v "$data_dir:/data" "$1" >/dev/null
  ready
  curl -fsS "$base_url/" >/dev/null
}

start_image vaultwarden/server:1.37.3
sudo test -s "$data_dir/db.sqlite3"
sudo touch "$data_dir/compatibility-sentinel"
docker rm -f "$container" >/dev/null

# Reuse exactly the same persistent volume and service settings.
start_image vaultwarden/server:1.37.3-alpine
sudo test -s "$data_dir/db.sqlite3"
sudo test -f "$data_dir/compatibility-sentinel"
echo "PASS: same 1.37.3 version, login UI, health and persistent DB with Alpine."
