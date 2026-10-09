#!/usr/bin/env bash
# Disposable persisted RDB test; NEVER attach a production Paperless directory.
set -euo pipefail
container=mrstore-paperless-redis-test
sandbox="$(mktemp -d)"
data_dir="$sandbox/data"
mkdir -p "$data_dir"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  sudo rm -rf "$sandbox"
}
trap cleanup EXIT

ready() {
  for i in $(seq 1 50); do
    if docker exec "$container" redis-cli ping 2>/dev/null | grep -q PONG; then
      return 0
    fi
    sleep 1
  done
  docker logs "$container" | tail -30
  echo "Redis startup failed" >&2
  return 1
}

start_broker() {
  docker run --name "$container" -d \
    -v "$data_dir:/data" "$1" >/dev/null
  ready
}

start_broker redis:8
docker exec "$container" redis-cli SET mrstore:compat "paperless-rdb-preserved" | grep -q OK
docker exec "$container" redis-cli SAVE | grep -q OK
sudo test -s "$data_dir/dump.rdb"
docker rm -f "$container" >/dev/null

start_broker redis:8.10.1-alpine
restored="$(docker exec "$container" redis-cli GET mrstore:compat)"
test "$restored" = "paperless-rdb-preserved"
docker exec "$container" redis-cli SET mrstore:second "ok" | grep -q OK
echo "PASS: Redis 8 RDB data remains usable after switching to pinned Alpine 8.10.1."
