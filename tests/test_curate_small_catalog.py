"""Curated public catalog removes others, but never fabricates CVE approval."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from curate_small_catalog import curate, PREFIX

SIX = ["homeassistant", "jellyfin", "immich", "nextcloud", "qbittorrent", "vaultwarden"]


def fixture(root, corrupt=False, approved=False):
    src, site = root / "source", root / "public"
    (src / "data").mkdir(parents=True)
    (src / "data/featured-apps.json").write_text(json.dumps({
        "schema": 1, "description": "Pilot", "apps": SIX}))
    for name in SIX:
        (src / "Apps" / name).mkdir(parents=True)
        (src / "Apps" / name / "docker-compose.yml").write_text("name: " + name)
    site.mkdir()
    ids = [PREFIX + name for name in SIX + ["steamos", "extra"]]
    main = {"version": 2, "app_count": len(ids), "apps": [{"id": x} for x in ids]}
    pt = {"apps": [{"id": x} for x in ids]}
    (site / "index.json").write_text(json.dumps(main))
    (site / "index.pt_PT.json").write_text(json.dumps(pt))
    for app in ids:
        folder = site / "apps" / app
        folder.mkdir(parents=True)
        (folder / "meta.json").write_text(json.dumps({"id": app}))
    with tarfile.open(site / "metadata.tar.gz", "w:gz") as archive:
        for name, content in [
            ("index.json", json.dumps(main).encode()),
            ("index.pt_PT.json", json.dumps(pt).encode()),
        ] + [(f"apps/{app}/meta.json", json.dumps({"id": app}).encode()) for app in ids]:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    digest = hashlib.sha256((site / "metadata.tar.gz").read_bytes()).hexdigest()
    (site / "metadata.sha256").write_text(
        ("0"*64 if corrupt else digest) + "  metadata.tar.gz\n")
    if approved:
        (site / "release-status.json").write_text("{}")
    return site, src


class CuratedCatalogTests(unittest.TestCase):
    def test_six_apps_locale_archive_and_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            site, src = fixture(Path(d))
            result = curate(site, src)
            self.assertEqual(result["public_apps"], 6)
            self.assertEqual(result["removed"], 2)
            self.assertFalse(result["certified_release"])
            self.assertEqual(len(json.loads((site / "index.json").read_text())["apps"]), 6)
            self.assertEqual(len(json.loads((site / "index.pt_PT.json").read_text())["apps"]), 6)
            with tarfile.open(site / "metadata.tar.gz") as archive:
                self.assertFalse(any("steamos" in n for n in archive.getnames()))
                self.assertEqual(len(json.load(archive.extractfile("index.json"))["apps"]), 6)
            self.assertEqual(len(list((site / "apps").iterdir())), 6)
            self.assertFalse(curate(site, src)["changed"])

    def test_checksum_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            site, src = fixture(Path(d), corrupt=True)
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                curate(site, src)
            self.assertEqual(len(json.loads((site / "index.json").read_text())["apps"]), 8)

    def test_cannot_overwrite_audited_release(self):
        with tempfile.TemporaryDirectory() as d:
            site, src = fixture(Path(d), approved=True)
            with self.assertRaisesRegex(ValueError, "Audited release"):
                curate(site, src)

    def test_missing_featured_manifest_fails(self):
        with tempfile.TemporaryDirectory() as d:
            site, src = fixture(Path(d))
            (src / "Apps/vaultwarden/docker-compose.yml").unlink()
            with self.assertRaisesRegex(ValueError, "missing source apps"):
                curate(site, src)


if __name__ == "__main__":
    unittest.main()
