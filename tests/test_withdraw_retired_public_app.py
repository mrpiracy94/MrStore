"""Checks emergency SteamOS withdrawal never adds/approves an app or corrupts metadata."""
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
from withdraw_retired_public_app import RETIRED, STEAM, withdraw


def fixture(root: Path, broken=False):
    site, src = root / "site", root / "source"
    site.mkdir()
    (src / "Apps/steam").mkdir(parents=True)
    (src / "Apps/steam/docker-compose.yml").write_text("name: steam\n")
    ids = [STEAM, RETIRED, "io.github.mrpiracy94.actual-budget"]
    idx = {"version": 2, "app_count": len(ids), "apps": [{"id": item} for item in ids]}
    loc = {"apps": [{"id": item} for item in ids]}
    (site / "index.json").write_text(json.dumps(idx))
    (site / "index.pt_PT.json").write_text(json.dumps(loc))
    for item in ids:
        (site / "apps" / item).mkdir(parents=True)
        (site / "apps" / item / "meta.json").write_text('{"id":"' + item + '"}')
    with tarfile.open(site / "metadata.tar.gz", "w:gz") as archive:
        for name, content in (
            ("index.json", json.dumps(idx).encode()),
            ("index.pt_PT.json", json.dumps(loc).encode()),
            ("apps/" + RETIRED + "/meta.json", RETIRED.encode()),
            ("apps/" + STEAM + "/meta.json", STEAM.encode()),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    digest = hashlib.sha256((site / "metadata.tar.gz").read_bytes()).hexdigest()
    (site / "metadata.sha256").write_text(("0" * 64 if broken else digest) + "  metadata.tar.gz\n")
    return site, src


class WithdrawalTests(unittest.TestCase):
    def test_atomic_removal_and_valid_metadata(self):
        with tempfile.TemporaryDirectory() as path:
            site, src = fixture(Path(path))
            result = withdraw(site, src)
            self.assertTrue(result["changed"])
            self.assertEqual(result["app_count"], 2)
            self.assertFalse(result["security_release_approved"])
            self.assertFalse((site / "apps" / RETIRED).exists())
            self.assertTrue((site / "apps" / STEAM / "meta.json").exists())
            self.assertEqual(json.loads((site / "index.json").read_text())["app_count"], 2)
            with tarfile.open(site / "metadata.tar.gz", "r:gz") as archive:
                self.assertTrue(all(RETIRED not in name for name in archive.getnames()))
                self.assertEqual(json.load(archive.extractfile("index.json"))["app_count"], 2)
            self.assertEqual(
                hashlib.sha256((site / "metadata.tar.gz").read_bytes()).hexdigest(),
                (site / "metadata.sha256").read_text().split()[0])

    def test_invalid_digest_keeps_old_public_index(self):
        with tempfile.TemporaryDirectory() as path:
            site, src = fixture(Path(path), broken=True)
            old = (site / "index.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                withdraw(site, src)
            self.assertEqual((site / "index.json").read_bytes(), old)

    def test_refuses_to_touch_verified_release_status(self):
        with tempfile.TemporaryDirectory() as path:
            site, src = fixture(Path(path))
            (site / "release-status.json").write_text('{"approved":[]}')
            with self.assertRaisesRegex(ValueError, "Audited catalog"):
                withdraw(site, src)

    def test_refuses_app_still_in_source(self):
        with tempfile.TemporaryDirectory() as path:
            site, src = fixture(Path(path))
            (src / "Apps/steamos").mkdir()
            (src / "Apps/steamos/docker-compose.yml").write_text("name: steamos")
            with self.assertRaisesRegex(ValueError, "SteamOS exists"):
                withdraw(site, src)

    def test_refuses_unknown_tar_payload_containing_steamos(self):
        with tempfile.TemporaryDirectory() as path:
            site, src = fixture(Path(path))
            with tarfile.open(site / "metadata.tar.gz", "w:gz") as tar:
                data = RETIRED.encode()
                header = tarfile.TarInfo("unknown.bin")
                header.size = len(data)
                tar.addfile(header, io.BytesIO(data))
            digest = hashlib.sha256((site / "metadata.tar.gz").read_bytes()).hexdigest()
            (site / "metadata.sha256").write_text(digest + "  metadata.tar.gz\n")
            with self.assertRaisesRegex(ValueError, "Unsupported SteamOS reference"):
                withdraw(site, src)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as path:
            site, src = fixture(Path(path))
            withdraw(site, src)
            self.assertEqual(withdraw(site, src)["changed"], False)


if __name__ == "__main__":
    unittest.main()
