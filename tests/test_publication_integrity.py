"""Regression tests for the generated release and catalog asset trust boundary.

No Docker, network, GitHub releases, or local installed services are touched.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import LOCAL_ASSET, local_asset_missing
from verify_dist import verify


class PublicationIntegrityTests(unittest.TestCase):
    APP = "io.github.example.sample"

    def make_release(self, root: Path) -> dict:
        app = root / "apps" / self.APP
        app.mkdir(parents=True)
        (app / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        (app / "meta.json").write_text("{}\n", encoding="utf-8")
        (root / "store.json").write_text('{"version": 2}\n', encoding="utf-8")
        entry = {
            "id": self.APP,
            "version": "1.0.0",
            "content_hash": "abc123ab",
            "compose_url": f"/apps/{self.APP}/docker-compose.yml",
            "meta_url": f"/apps/{self.APP}/meta.json",
            "icon": "https://example.org/icon.svg",
        }
        return {"version": 2, "app_count": 1, "apps": [entry]}

    @staticmethod
    def write_index(root: Path, index: dict) -> None:
        (root / "index.json").write_text(json.dumps(index), encoding="utf-8")

    def test_valid_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = self.make_release(root)
            self.write_index(root, index)
            self.assertEqual(verify(root, 1), 1)

    def test_cannot_redirect_to_external_compose_or_metadata(self):
        for field in ("compose_url", "meta_url"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                index = self.make_release(root)
                index["apps"][0][field] = "https://example.org/malicious.yml"
                self.write_index(root, index)
                with self.assertRaisesRegex(ValueError, f"invalid generated {field}"):
                    verify(root, 1)

    def test_cannot_link_to_another_existing_app_files(self):
        for field, filename in (("compose_url", "docker-compose.yml"),
                                ("meta_url", "meta.json")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                index = self.make_release(root)
                other = root / "apps" / "io.github.example.other"
                other.mkdir(parents=True)
                (other / filename).write_text("exists\n", encoding="utf-8")
                index["apps"][0][field] = f"/apps/io.github.example.other/{filename}"
                self.write_index(root, index)
                with self.assertRaisesRegex(ValueError, f"invalid generated {field}"):
                    verify(root, 1)

    def test_generated_icon_cannot_escape_with_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            index = self.make_release(root)
            file = Path(outside) / "secret.svg"
            file.write_text("<svg/>", encoding="utf-8")
            link = root / "apps" / self.APP / "icon.svg"
            try:
                link.symlink_to(file)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks not available")
            index["apps"][0]["icon"] = f"/apps/{self.APP}/icon.svg"
            self.write_index(root, index)
            with self.assertRaisesRegex(ValueError, "broken generated icon"):
                verify(root, 1)

    def test_local_catalog_asset_cannot_escape_with_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            file = Path(outside) / "secret.svg"
            file.write_text("<svg/>", encoding="utf-8")
            link = root / "icon.svg"
            try:
                link.symlink_to(file)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks not available")
            self.assertIn("unsafe", local_asset_missing(LOCAL_ASSET + "icon.svg", root))


if __name__ == "__main__":
    unittest.main()
