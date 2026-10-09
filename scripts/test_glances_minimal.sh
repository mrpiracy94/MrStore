#!/usr/bin/env bash
set -euo pipefail
container="mrstore-glances-minimal-smoke"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$container" \
  -p 127.0.0.1:16128:61208 \
  -e "GLANCES_OPT=-w" \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  nicolargo/glances:latest >/dev/null

for attempt in $(seq 1 90); do
  if curl -fsSL --max-time 3 "http://127.0.0.1:16128/" -o /dev/null 2>/dev/null; then
    echo "PASS: minimal Glances serves its web interface on port 61208."
    exit 0
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$container")" != true ]]; then
    docker logs "$container" | tail -50
    echo "Glances container stopped unexpectedly" >&2
    exit 1
  fi
  sleep 2
done

docker logs "$container" | tail -50
echo "Glances web UI did not respond" >&2
exit 1
