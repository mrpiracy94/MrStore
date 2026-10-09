#!/usr/bin/env bash
set -euo pipefail
arch="${1:?architecture required}"
case "$arch" in amd64|arm64) ;; *) exit 2;; esac
folder="$(mktemp -d)"
name="mrstore-phpmyadmin-test-$arch"
mkdir -p "$folder/config"
touch "$folder/config/preexisting-settings-sentinel"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; sudo rm -rf "$folder"; }
trap cleanup EXIT
docker run -d --platform linux/$arch --name "$name" \
  -p 127.0.0.1:28080:80 \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Lisbon -e PMA_ARBITRARY=1 \
  -v "$folder/config:/config" "mrstore-phpmyadmin-patched:$arch" >/dev/null
for i in $(seq 1 100); do
  code="$(curl --silent --show-error --location --max-time 4 --output "$folder/login.html" --write-out '%{http_code}' http://127.0.0.1:28080/ 2>/dev/null || :)"
  if [[ "$code" == "200" ]] && grep -Eiq '(pma_username|phpMyAdmin)' "$folder/login.html"; then
    test -f "$folder/config/preexisting-settings-sentinel"
    echo "PASS: $arch LSIO phpMyAdmin renders its login page, preserves /config and nginx port 80."
    exit 0
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$name")" != true ]]; then
    docker logs "$name" | tail -70
    exit 1
  fi
  sleep 2
done
docker logs "$name" | tail -70
exit 1
