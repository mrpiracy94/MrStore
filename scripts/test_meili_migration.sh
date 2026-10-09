#!/usr/bin/env bash
# Disposable migration test: NEVER mount live ZimaOS data here.
set -euo pipefail

old_name="mrstore-meili-old"
new_name="mrstore-meili-new"
work_dir="$(mktemp -d)"
db_dir="$work_dir/meili"
backup_dir="$work_dir/backup"
key="mrstore-ephemeral-migration-test-key-123"
new_image="${NEW_IMAGE:-getmeili/meilisearch:v1.54.3@sha256:e68913ab7d6f5b159529e472cfd362ce3c741fafd3c127961b2142abbe41b3c9}"
url="http://127.0.0.1:17700"
mkdir -p "$db_dir"

cleanup() {
  docker logs "$old_name" 2>/dev/null | tail -20 || true
  docker logs "$new_name" 2>/dev/null | tail -30 || true
  docker rm -f "$old_name" "$new_name" >/dev/null 2>&1 || true
  sudo rm -rf "$work_dir"
}
trap cleanup EXIT

ready() {
  for i in $(seq 1 100); do
    if curl -fsS "$url/health" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  echo "Meilisearch did not become ready" >&2
  return 1
}

check_document() {
  for i in $(seq 1 80); do
    if curl -fsS -H "Authorization: Bearer $key" \
      "$url/indexes/bookmarks/documents/42" 2>/dev/null |
      jq -e '.id == 42 and .title == "persisted bookmark"' >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "Migration lost the indexed bookmark" >&2
  return 1
}

docker run -d --name "$old_name" -p 127.0.0.1:17700:7700 \
  -e "MEILI_MASTER_KEY=$key" -v "$db_dir:/meili_data" \
  getmeili/meilisearch:v1.13.3 >/dev/null
ready

curl -fsS -X POST -H "Authorization: Bearer $key" \
  -H "Content-Type: application/json" \
  --data '{"uid":"bookmarks","primaryKey":"id"}' \
  "$url/indexes" >/dev/null
curl -fsS -X POST -H "Authorization: Bearer $key" \
  -H "Content-Type: application/json" \
  --data '[{"id":42,"title":"persisted bookmark"}]' \
  "$url/indexes/bookmarks/documents" >/dev/null
check_document

docker stop "$old_name" >/dev/null
docker rm "$old_name" >/dev/null

# Copy the old DB *while stopped*. A separate backup is essential for rollback.
sudo cp -a "$db_dir" "$backup_dir"
test -d "$backup_dir"

docker run -d --name "$new_name" -p 127.0.0.1:17700:7700 \
  -e "MEILI_MASTER_KEY=$key" -v "$db_dir:/meili_data" \
  "$new_image" meilisearch --upgrade-db >/dev/null
ready
check_document

# A new Meilisearch instance must also reopen the upgraded database safely.
docker stop "$new_name" >/dev/null
docker rm "$new_name" >/dev/null
docker run -d --name "$new_name" -p 127.0.0.1:17700:7700 \
  -e "MEILI_MASTER_KEY=$key" -v "$db_dir:/meili_data" \
  "$new_image" meilisearch --upgrade-db >/dev/null
ready
check_document
echo "PASS: bookmark persisted after migration and second restart of new Meilisearch."
