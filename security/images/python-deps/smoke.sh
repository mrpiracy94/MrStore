#!/usr/bin/env bash
set -euo pipefail

app="${1:?App required}"
arch="${2:?Architecture required}"
case "$app" in
  bazarr|beets|limnoria|nzbget|sickgear|tautulli) ;;
  *) echo "Unsupported app: $app" >&2; exit 2 ;;
esac
case "$arch" in amd64|arm64) ;; *) exit 2 ;; esac

image="mrstore-python-deps:$app-$arch"
name="mrstore-python-test-$app-$arch"
root="$(mktemp -d)"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  sudo rm -rf "$root"
}
trap cleanup EXIT

# The actual bundled interpreter must contain the corrected versions.
docker run --rm --platform "linux/$arch" --entrypoint /lsiopy/bin/python "$image" -c '
from importlib.metadata import version
for pkg, expected in (("msgpack","1.2.1"),("urllib3","2.8.0"),("setuptools","80.9.0")):
    actual=version(pkg)
    assert actual == expected, (pkg, actual, expected)
print("PASS Python versions")
'

mkdir -p "$root/config"
printf 'preserve-me\n' > "$root/config/mrstore-test-sentinel"

if [[ "$app" == beets ]]; then
  docker run --rm --platform "linux/$arch" --entrypoint /bin/sh "$image" -c \
    'command -v beet >/dev/null || test -x /lsiopy/bin/beet'
  echo "PASS $app/$arch CLI present"
  exit 0
fi

case "$app" in
  bazarr) port=6767; kind=http ;;
  tautulli) port=8181; kind=http ;;
  nzbget) port=6789; kind=http ;;
  sickgear) port=8081; kind=http ;;
  limnoria) port=6667; kind=tcp ;;
esac

docker run --detach --platform "linux/$arch" --name "$name" \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Lisbon \
  -p "127.0.0.1:28080:$port" \
  -v "$root/config:/config" "$image" >/dev/null

for attempt in $(seq 1 45); do
  if [[ "$(docker inspect -f '{{.State.Running}}' "$name")" != true ]]; then
    echo "FAIL $app/$arch container stopped" >&2
    docker logs "$name" | tail -40
    exit 1
  fi
  if [[ "$kind" == http ]]; then
    status="$(curl -sS -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:28080/ || true)"
    [[ "$status" =~ ^[234][0-9][0-9]$ ]] && break
  else
    (echo >/dev/tcp/127.0.0.1/28080) >/dev/null 2>&1 && break
  fi
  sleep 2
done

if [[ "$kind" == http ]]; then
  [[ "${status:-}" =~ ^[234][0-9][0-9]$ ]] || { echo "FAIL $app HTTP" >&2; exit 1; }
else
  (echo >/dev/tcp/127.0.0.1/28080) >/dev/null 2>&1 || { echo "FAIL $app TCP" >&2; exit 1; }
fi

# The test must not erase application data during startup.
test "$(cat "$root/config/mrstore-test-sentinel")" = preserve-me
echo "PASS $app/$arch startup, port $port and /config"
