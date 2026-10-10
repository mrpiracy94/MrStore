"""Source provenance and staging regressions; tests never access the network."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from scripts.official_screenshots import (
    SOURCES, UPSTREAM_COMMIT, import_screenshots, verify_image,
)


class VerifiedScreenshotsTests(unittest.TestCase):
    def test_sources_have_unique_safe_locations_and_pinned_hashes(self):
        self.assertEqual(40, len(UPSTREAM_COMMIT))
        self.assertGreaterEqual(len(SOURCES), 10)
        keys = set()
        for app, upstream, filename, sha in SOURCES:
            self.assertNotIn((app, filename), keys)
            keys.add((app, filename))
            self.assertTrue(app.replace("-", "").isalnum())
            self.assertTrue(upstream.replace("-", "").isalnum())
            self.assertTrue(filename.startswith("screenshot-"))
            self.assertEqual(filename, Path(filename).name)
            self.assertIn(Path(filename).suffix, {".png", ".jpg", ".jpeg"})
            self.assertEqual(40, len(sha))
            int(sha, 16)

    def test_git_object_hash_and_image_signature(self):
        data = b"\x89PNG\r\n\x1a\n" + b"data" * 50
        sha = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        verify_image(data, ".png", sha)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            verify_image(data + b"modification", ".png", sha)
        with self.assertRaisesRegex(ValueError, "Not a JPEG"):
            verify_image(data, ".jpg", sha)

    def test_staging_does_not_modify_unapproved_apps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Apps").mkdir()
            with patch("scripts.official_screenshots.download") as download:
                result = import_screenshots(root)
                download.assert_not_called()
            self.assertEqual(0, result["errors"])
            self.assertEqual(0, result["verified"])
            self.assertEqual(len(SOURCES), len(result["records"]))

    def test_verify_only_does_not_create_files(self):
        data = b"\x89PNG\r\n\x1a\n" + b"data" * 50
        sha = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app_dir = root / "Apps/test"
            app_dir.mkdir(parents=True)
            (app_dir / "docker-compose.yml").write_text("services: {}")
            with patch("scripts.official_screenshots.SOURCES",
                       (("test", "Test", "screenshot-1.png", sha),)), patch(
                       "scripts.official_screenshots.download", return_value=data):
                result = import_screenshots(root, verify_only=True)
            self.assertEqual(1, result["verified"])
            self.assertEqual(0, result["imported"])
            self.assertFalse((app_dir / "screenshot-1.png").exists())


if __name__ == "__main__":
    unittest.main()
