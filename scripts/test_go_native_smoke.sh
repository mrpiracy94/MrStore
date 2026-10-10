#!/usr/bin/env bash
set -euo pipefail
APP="$1"; IMAGE="$2"; ARCH="$3"
if [[ "$APP" != gitea && "$APP" != qui ]]; then echo 'invalid app' >&2; exit 2; fi
actual="$(docker image inspect "$IMAGE" --format '{{.Architecture}}')"
[[ "$actual" == "$ARCH" ]] || { echo "Expected $ARCH, got $actual" >&2; exit 1; }
native="$(uname -m)"
case "$ARCH:$native" in amd64:x86_64|arm64:aarch64) ;; *) echo "Not native $ARCH runner: $native" >&2; exit 1;; esac
work="$(mktemp -d)"
cid=""
cleanup() { if [[ -n "$cid" ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/data"
if [[ "$APP" == gitea ]]; then
  docker run --rm --entrypoint /app/gitea/gitea "$IMAGE" --version | grep -F '28.1.0'
  cid="$(docker run -d --name "mrstore-smoke-gitea-$ARCH-$$" \
    -p 127.0.0.1::3000 -p 127.0.0.1::22 \
    -e USER_UID=1000 -e USER_GID=1000 -e TZ=Europe/Lisbon \
    -v "$work/data:/data" "$IMAGE")"
  http_port="$(docker port "$cid" 3000/tcp | sed -n 's/.*://p' | head -1)"
  ssh_port="$(docker port "$cid" 22/tcp | sed -n 's/.*://p' | head -1)"
  [[ "$http_port" =~ ^[0-9]+$ && "$ssh_port" =~ ^[0-9]+$ ]]
  for _ in $(seq 1 120); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$http_port/" -o /dev/null; then break; fi
    sleep 2
  done
  curl -fsS --max-time 10 "http://127.0.0.1:$http_port/" -o /dev/null
  timeout 5 bash -c "echo >/dev/tcp/127.0.0.1/$ssh_port"
else
  docker run --rm --entrypoint /usr/local/bin/qui "$IMAGE" --version
  cid="$(docker run -d --name "mrstore-smoke-qui-$ARCH-$$" \
    -p 127.0.0.1::7476 -e TZ=Europe/Lisbon \
    -v "$work/data:/config" "$IMAGE")"
  http_port="$(docker port "$cid" 7476/tcp | sed -n 's/.*://p' | head -1)"
  [[ "$http_port" =~ ^[0-9]+$ ]]
  for _ in $(seq 1 75); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$http_port/health" -o /dev/null; then break; fi
    sleep 2
  done
  curl -fsS --max-time 10 "http://127.0.0.1:$http_port/health" -o /dev/null
fi
echo "mrstore-$APP-$ARCH" > "$work/data/.mrstore-smoke"
docker restart "$cid" >/dev/null
if [[ "$APP" == gitea ]]; then
  for _ in $(seq 1 120); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$http_port/" -o /dev/null; then break; fi
    sleep 2
  done
  curl -fsS --max-time 10 "http://127.0.0.1:$http_port/" -o /dev/null
  timeout 5 bash -c "echo >/dev/tcp/127.0.0.1/$ssh_port"
else
  for _ in $(seq 1 75); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$http_port/health" -o /dev/null; then break; fi
    sleep 2
  done
  curl -fsS --max-time 10 "http://127.0.0.1:$http_port/health" -o /dev/null
fi
[[ "$(cat "$work/data/.mrstore-smoke")" == "mrstore-$APP-$ARCH" ]]
echo "$APP/$ARCH: HTTP, bind volume, restart, ports verified"
