#!/usr/bin/env bash
# Validate this specific rebase changes nginx OS packages, not the web app.
# Usage: bash scripts/test_it_tools_rebase.sh amd64|arm64
set -euo pipefail
arch="${1:?architecture required}"
case "$arch" in amd64|arm64) ;; *) echo "Unsupported arch" >&2; exit 1;; esac
old="corentinth/it-tools@sha256:8b8128748339583ca951af03dfe02a9a4d7363f61a216226fc28030731a5a61f"
new="mrstore-it-tools:patched-$arch"
work="$(mktemp -d)"
old_id=""
new_id=""
running=""
cleanup() {
  test -z "$running" || docker rm -f "$running" >/dev/null 2>&1 || true
  test -z "$old_id" || docker rm -f "$old_id" >/dev/null 2>&1 || true
  test -z "$new_id" || docker rm -f "$new_id" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/upstream/html" "$work/patched/html"
# Pull the architecture-specific manifest, not the common multiarch index.
# Docker's classic image store otherwise tries to overwrite a previously pulled
# platform digest when we verify AMD64 and then ARM64 in the same job.
child_digest="$(docker buildx imagetools inspect "$old" --raw | jq -er --arg arch "$arch" '[.manifests[] | select(.platform.os == "linux" and .platform.architecture == $arch) | .digest][0]')"
[[ "$child_digest" =~ ^sha256:[a-f0-9]{64}$ ]]
old_id="$(docker create --platform "linux/$arch" "corentinth/it-tools@$child_digest")"
new_id="$(docker create --platform "linux/$arch" "$new")"
docker cp "$old_id:/usr/share/nginx/html/." "$work/upstream/html/"
docker cp "$new_id:/usr/share/nginx/html/." "$work/patched/html/"
docker cp "$old_id:/etc/nginx/conf.d/default.conf" "$work/upstream/default.conf"
docker cp "$new_id:/etc/nginx/conf.d/default.conf" "$work/patched/default.conf"
diff -qr "$work/upstream/html" "$work/patched/html"
cmp "$work/upstream/default.conf" "$work/patched/default.conf"
echo "PASS: $arch original HTML, JS/CSS and nginx routing are byte-for-byte identical."
docker run -d --platform "linux/$arch" --name mrstore-it-tools-ci \
  -p 127.0.0.1:18085:80 "$new" >/dev/null
running="mrstore-it-tools-ci"
for n in $(seq 1 90); do
  if curl -fsSL --max-time 3 http://127.0.0.1:18085/ -o "$work/response.html"; then
    test -s "$work/response.html"
    echo "PASS: $arch patched static UI serves HTTP on port 80."
    exit 0
  fi
  sleep 2
done
docker logs "$running" | tail -50
echo "Patched IT-Tools HTTP endpoint was not ready" >&2
exit 1
