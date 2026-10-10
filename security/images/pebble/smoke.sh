#!/usr/bin/env bash
set -euo pipefail
app="$1"
arch="$2"
case "$app" in jellyfin|plex|ffmpeg) ;; *) echo "Unsupported app" >&2; exit 2 ;; esac
case "$arch" in amd64|arm64) ;; *) exit 2 ;; esac
image="mrstore-pebble:$app-$arch"
docker run --rm --platform "linux/$arch" --entrypoint /usr/bin/pebble "$image" version
if [[ "$app" == ffmpeg ]]; then
  docker run --rm --platform "linux/$arch" --entrypoint /bin/sh "$image" -c \
    'ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc2=size=128x128:rate=1 -frames:v 1 -f null -'
  echo "PASS: $app $arch actual FFmpeg conversion"
  exit 0
fi
work="$(mktemp -d)"
name="mrstore-pebble-$app-$arch"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || :; sudo rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/config"
printf 'untouched\n' > "$work/config/sentinel"
case "$app" in
  jellyfin) port=8096; path="/" ;;
  plex) port=32400; path="/web" ;;
esac
docker run -d --platform "linux/$arch" --name "$name" \
  -p "127.0.0.1::$port" \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Lisbon -e VERSION=docker \
  -v "$work/config:/config" "$image" >/dev/null
published="$(docker port "$name" "$port/tcp" | head -1)"
hostport="$(printf '%s' "$published" | awk -F: '{print $NF}')"
[[ "$hostport" =~ ^[0-9]+$ ]]
for attempt in $(seq 1 120); do
  if [[ "$(docker inspect -f '{{.State.Running}}' "$name")" != true ]]; then
    docker logs "$name" | tail -65
    echo "FAIL: $app stopped before ready" >&2
    exit 1
  fi
  status="$(curl --silent --max-time 4 -L -o /dev/null -w '%{http_code}' "http://127.0.0.1:$hostport$path" || :)"
  if [[ "$status" =~ ^[23][0-9][0-9]$ ]]; then
    test "$(cat "$work/config/sentinel")" = "untouched"
    echo "PASS: $app $arch real HTTP $status, preserved /config"
    exit 0
  fi
  sleep 3
done
docker logs "$name" | tail -65
echo "FAIL: $app $arch no successful HTTP response" >&2
exit 1
