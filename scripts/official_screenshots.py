"""Vendor authentic upstream screenshots only for approved, staged ZimaOS apps.

Each image is pinned by its Git blob SHA and an immutable upstream commit.
Never trusts image filenames, executable content, or downloaded response headers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "0909364b800950030e71ea82355a5969a1c08b39"
UPSTREAM = "https://raw.githubusercontent.com/IceWhaleTech/CasaOS-AppStore/" + UPSTREAM_COMMIT
MAX_IMAGE_BYTES = 3 * 1024 * 1024

# app folder, source folder, screenshot filename, immutable Git blob SHA-1
SOURCES = (
    ("gitea", "Gitea", "screenshot-1.png", "836b11f808d50b2a976e5aa13c62b24994ca8b89"),
    ("homeassistant", "HomeAssistant", "screenshot-1.jpg", "cea9470e2c46fd08e5bbb99660db63aef3291e3d"),
    ("jellyfin", "Jellyfin", "screenshot-1.png", "2951abbbf43112fdcb56cce480b8059a9c6bd9c9"),
    ("ollama", "Ollama", "screenshot-1.png", "fee5034c0dc79c8440580a034ff1b1fb79159cd0"),
    ("plex", "Plex", "screenshot-1.png", "7d6678b3586d738fcfd544e23c649f5dd78cbf6d"),
    ("qbittorrent", "qBittorrent", "screenshot-1.png", "ef25900d740840f9948cc26a435082eae48e97e2"),
    ("syncthing", "Syncthing", "screenshot-1.png", "05813cd41ba2d934c3023b3dae05cf7147b986ac"),
    ("immich", "Immich", "screenshot-2.png", "8627eb0e7b1c78749928e38c8193dbb85e7cda7b"),
    ("nextcloud", "Nextcloud", "screenshot-2.png", "baefed662c5489fedffab3e63ef793069302d123"),
    ("vaultwarden", "Vaultwarden", "screenshot-2.png", "f95686be3f5fc934440356763b1a22a586ed85ea"),
)


def verify_image(data: bytes, extension: str, blob_sha: str) -> None:
    if len(data) < 128 or len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image size outside 128..{MAX_IMAGE_BYTES} bytes")
    if extension == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Not a PNG screenshot")
    if extension in (".jpg", ".jpeg") and not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("Not a JPEG screenshot")
    git_hash = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
    if git_hash != blob_sha:
        raise ValueError(f"Screenshot content mismatch: expected {blob_sha}, got {git_hash}")


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "MrStore-screenshot-provenance/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if not response.url.startswith("https://"):
            raise ValueError("Non-HTTPS image redirect rejected")
        value = response.read(MAX_IMAGE_BYTES + 1)
    return value


def import_screenshots(root: Path, verify_only: bool = False) -> dict:
    records = []
    for app, upstream, name, sha in SOURCES:
        directory = root / "Apps" / app
        if not (directory / "docker-compose.yml").is_file():
            records.append({"app": app, "filename": name, "status": "not-in-catalog"})
            continue  # Staged release excludes quarantined apps.
        url = f"{UPSTREAM}/Apps/{upstream}/{name}"
        dest = directory / name
        record = {"app": app, "filename": name, "source": url, "upstream_blob_sha": sha}
        try:
            content = download(url)
            verify_image(content, Path(name).suffix.lower(), sha)
            if dest.exists():
                if dest.read_bytes() != content:
                    raise ValueError("Existing screenshot differs from pinned official asset")
                record["status"] = "already-present"
            elif verify_only:
                record["status"] = "verified-remote"
            else:
                # Write complete content atomically. Never touch Compose manifests.
                with tempfile.NamedTemporaryFile(dir=directory, prefix=".screenshot-", delete=False) as tmp:
                    tmp.write(content)
                    temp_name = tmp.name
                try:
                    os.replace(temp_name, dest)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
                record["status"] = "imported"
        except (OSError, ValueError) as exc:
            record["status"] = "error"
            record["error"] = str(exc)[:300]
        records.append(record)
    return {"upstream_commit": UPSTREAM_COMMIT, "records": records,
            "errors": sum(x["status"] == "error" for x in records),
            "imported": sum(x["status"] == "imported" for x in records),
            "verified": sum(x["status"] in ("imported", "already-present", "verified-remote")
                            for x in records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--verify-only", action="store_true",
                        help="Download and hash-check source images without modifying files.")
    parser.add_argument("--report", type=Path, default=ROOT / "out/screenshot-provenance.json")
    args = parser.parse_args()
    results = import_screenshots(args.root, args.verify_only)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"verified": results["verified"], "imported": results["imported"],
                      "errors": results["errors"]}, indent=2))
    for record in results["records"]:
        if record["status"] == "error":
            print(f"ERROR: {record['app']}: {record.get('error')}")
    return int(results["errors"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
