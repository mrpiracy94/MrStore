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
cleanup() {
  local rc=$?
  trap - EXIT
  set +e
  if [[ -n "$cid" ]]; then
    if (( rc != 0 )); then
      echo "::error::${APP}/${ARCH} runtime smoke failed; container diagnostics follow" >&2
      docker inspect --format 'status={{.State.Status}} exit={{.State.ExitCode}} error={{.State.Error}}' "$cid" >&2 || true
      docker logs --tail 120 "$cid" >&2 || true
    fi
    docker rm -f "$cid" >/dev/null 2>&1 || true
  fi
  # Rootful images may write files owned by other UIDs into this temporary bind mount.
  # GitHub-hosted Ubuntu runners provide passwordless sudo; do not hide smoke failures.
  sudo rm -rf -- "$work" || true
  exit "$rc"
}
trap cleanup EXIT
wait_for_http() {
  local url="$1" attempts="$2"
  local n
  for ((n=0; n<attempts; n++)); do
    # Hosted runners may set an HTTP proxy; localhost Docker published ports
    # must be reached directly, not through the proxy.
    if curl --noproxy "*" -fsS --max-time 3 "$url" -o /dev/null 2>/dev/null; then return 0; fi
    if [[ "$(docker inspect --format '{{.State.Running}}' "$cid")" != true ]]; then
      echo "::error::Container stopped before HTTP readiness: $url" >&2
      return 1
    fi
    sleep 2
  done
  echo "::error::Timed out waiting for HTTP readiness: $url" >&2
  curl --noproxy "*" -v --max-time 5 "$url" -o /dev/null 2>&1 || true
  docker port "$cid" >&2 || true
  return 1
}
mkdir -p "$work/data"
if [[ "$APP" == gitea ]]; then
  docker run --rm --entrypoint /app/gitea/gitea "$IMAGE" --version | grep -F '28.1.0'
  cid="$(docker run -d --name "mrstore-smoke-gitea-$ARCH-$$" \
    -p 127.0.0.1::3000 -p 127.0.0.1::22 \
    -e USER_UID=1000 -e USER_GID=1000 -e TZ=Europe/Lisbon \
    -v "$work/data:/data" "$IMAGE")"
  http_port="$(docker inspect --format '{{(index (index .NetworkSettings.Ports "3000/tcp") 0).HostPort}}' "$cid")"
  ssh_port="$(docker inspect --format '{{(index (index .NetworkSettings.Ports "22/tcp") 0).HostPort}}' "$cid")"
  [[ "$http_port" =~ ^[0-9]+$ && "$ssh_port" =~ ^[0-9]+$ ]]
  docker port "$cid"
  wait_for_http "http://127.0.0.1:$http_port/" 120
  timeout 5 bash -c "echo >/dev/tcp/127.0.0.1/$ssh_port"
else
  docker run --rm --entrypoint /usr/local/bin/qui "$IMAGE" --version
  cid="$(docker run -d --name "mrstore-smoke-qui-$ARCH-$$" \
    -p 127.0.0.1::7476 -e TZ=Europe/Lisbon \
    -v "$work/data:/config" "$IMAGE")"
  http_port="$(docker inspect --format '{{(index (index .NetworkSettings.Ports "7476/tcp") 0).HostPort}}' "$cid")"
  [[ "$http_port" =~ ^[0-9]+$ ]]
  docker port "$cid"
  wait_for_http "http://127.0.0.1:$http_port/health" 75
fi
echo "mrstore-$APP-$ARCH" > "$work/data/.mrstore-smoke"
docker restart "$cid" >/dev/null
if [[ "$APP" == gitea ]]; then
  wait_for_http "http://127.0.0.1:$http_port/" 120
  timeout 5 bash -c "echo >/dev/tcp/127.0.0.1/$ssh_port"
else
  wait_for_http "http://127.0.0.1:$http_port/health" 75
fi
[[ "$(cat "$work/data/.mrstore-smoke")" == "mrstore-$APP-$ARCH" ]]
echo "$APP/$ARCH: HTTP, bind volume, restart, ports verified"
