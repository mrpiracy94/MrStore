#!/usr/bin/env bash
# Check actual basic-ftp 6 API against a disposable local FTP server,
# not only that Code Server starts on port 8443.
set -euo pipefail
arch="${1:?architecture required}"
case "$arch" in amd64|arm64) ;; *) exit 2;; esac
work="$(mktemp -d)"
cid=""
ftp_pid=""
cleanup() {
  test -z "$ftp_pid" || kill "$ftp_pid" 2>/dev/null || true
  test -z "$cid" || docker rm -f "$cid" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/root"
echo "MrStore FTP compatibility sentinel" > "$work/root/sentinel.txt"
cid="$(docker create --platform linux/$arch "mrstore-code-server-patched:$arch")"
docker cp "$cid:/app/code-server/node_modules/basic-ftp" "$work/basic-ftp"
python -m pip install --quiet pyftpdlib==2.0.1
python -m pyftpdlib -i 127.0.0.1 -p 23813 -d "$work/root" \
  -u mrstore -P test-password > "$work/ftp.log" 2>&1 &
ftp_pid="$!"
for i in $(seq 1 40); do
  if (echo > /dev/tcp/127.0.0.1/23813) >/dev/null 2>&1; then break; fi
  sleep 1
done
node - "$work/basic-ftp" <<'JS'
const { Client } = require(process.argv[2]);
(async () => {
  const ftp = new Client(10000);
  try {
    await ftp.access({
      host: "127.0.0.1",
      port: 23813,
      user: "mrstore",
      password: "test-password",
      secure: false,
    });
    const files = await ftp.list();
    if (!files.some(file => file.name === "sentinel.txt")) {
      throw new Error("Patched basic-ftp cannot list the server's file");
    }
    console.log("PASS: basic-ftp 6 authenticates and lists a file over real FTP.");
  } finally {
    ftp.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
JS
