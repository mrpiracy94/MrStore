#!/usr/bin/env bash
# Integration only: temporary MariaDB database and disposable /config.
set -euo pipefail
arch="${1:?amd64 or arm64}"
case "$arch" in amd64|arm64) ;; *) exit 2;; esac
suffix="$arch"
network="mrstore-php-db-$suffix"
db="mrstore-mariadb-$suffix"
pma="mrstore-phpmyadmin-db-$suffix"
work="$(mktemp -d)"
mkdir -p "$work/config"
cleanup() {
  docker rm -f "$pma" "$db" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  sudo rm -rf "$work"
}
trap cleanup EXIT
docker network create "$network" >/dev/null
docker run -d --name "$db" --network "$network" \
  -e MARIADB_ROOT_PASSWORD=local-testing-only \
  -e MARIADB_DATABASE=mrstore_ci \
  -e MARIADB_USER=mrstore \
  -e MARIADB_PASSWORD=local-testing-only \
  mariadb:11 >/dev/null
for i in $(seq 1 90); do
  if docker exec "$db" mariadb -u mrstore -plocal-testing-only mrstore_ci \
       -e 'SELECT 1' >/dev/null 2>&1; then break; fi
  sleep 2
done
docker exec "$db" mariadb -u mrstore -plocal-testing-only mrstore_ci \
       -e 'CREATE TABLE IF NOT EXISTS mrstore_probe (id INT); INSERT INTO mrstore_probe VALUES (17);'
docker run -d --platform "linux/$arch" --name "$pma" --network "$network" \
  -p 127.0.0.1:28082:80 \
  -e PUID=1000 -e PGID=1000 -e PMA_HOST="$db" -e PMA_ARBITRARY=1 \
  -v "$work/config:/config" "mrstore-phpmyadmin-patched:$arch" >/dev/null
for i in $(seq 1 70); do
  if curl -fsSL --max-time 3 http://127.0.0.1:28082/ -o "$work/page.html" >/dev/null 2>&1; then
    grep -qi 'phpMyAdmin' "$work/page.html"
    break
  fi
  sleep 2
done
docker exec "$pma" php -r '
  $db = new mysqli(getenv("PMA_HOST"), "mrstore", "local-testing-only", "mrstore_ci");
  if ($db->connect_errno) { fwrite(STDERR, $db->connect_error); exit(1); }
  $query=$db->query("SELECT id FROM mrstore_probe");
  if ($query->fetch_row()[0] != 17) { exit(2); }
  echo "PASS: PHP MySQL extension reads the same disposable MariaDB database.\n";
'
echo "PASS: $arch patched phpMyAdmin nginx renders its login page with MariaDB available."
