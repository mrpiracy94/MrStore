"""HDS 1.0 and .hdstore bundle structural regression tests."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from scripts.export_homedock import brand_icon, make_hds, validate_hds, build
SHA = "a" * 64


class HomeDockTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.source = self.root / "release-source"
        apps = self.source / "Apps" / "demo"
        apps.mkdir(parents=True)
        self.compose = (f"name: demo\nservices:\n  demo:\n"
                        f"    image: example/demo@sha256:{SHA}\n"
                        "x-casaos:\n  id: io.github.mrpiracy94.demo\n"
                        "  main: demo\n  title:\n    en_US: Demo\n"
                        "  category: Media\n")
        (apps / "docker-compose.yml").write_text(self.compose)
        for n in ("store-config.json", "supported-languages.json",
                  "category-list.json", "recommend-list.json"):
            (self.source / n).write_text("[]")
        self.selection = self.root / "selection.json"
        self.selection.write_text(json.dumps({"approved": ["demo"], "approved_count": 1}))

    def test_hds_structure_icon_integrity(self):
        binary, manifest = make_hds("demo", self.compose.encode())
        self.assertLess(len(binary), 5_000_000)
        with ZipFile(io.BytesIO(binary)) as archive:
            self.assertEqual(set(archive.namelist()), {
                "manifest.json", "docker-compose.yml", "icon.png", ".hds_signature"})
            self.assertEqual(archive.read("icon.png")[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(manifest["category"], "Media")
            self.assertEqual(manifest["docker_image"], "example/demo@sha256:" + SHA)
        self.assertEqual(validate_hds(binary)["name"], "demo")

    def test_reject_tampered_package(self):
        binary, _ = make_hds("demo", self.compose.encode())
        with ZipFile(io.BytesIO(binary)) as source:
            parts = {name: source.read(name) for name in source.namelist()}
        parts["docker-compose.yml"] = b"image: malicious:latest"
        from scripts.export_homedock import pack_zip
        with self.assertRaisesRegex(ValueError, "integrity"):
            validate_hds(pack_zip(parts))

    def test_homestore_signature_matches_inner_bytes(self):
        data = build(self.source, self.selection, self.root / "dist" / "homedock")
        self.assertEqual(data["exported_count"], 1)
        package = self.root / "dist/homedock/demo.hds"
        self.assertEqual(validate_hds(package.read_bytes())["name"], "demo")
        with ZipFile(self.root / "dist/homedock/mrstore.hdstore") as bundle:
            items = json.loads(bundle.read("store_manifest.json"))
            self.assertEqual(items["package_count"], 1)
            actual = hashlib.sha256(bundle.read("store_manifest.json") +
                bundle.read("packages/demo.hds")).hexdigest()
            self.assertEqual(bundle.read(".hdstore_signature").decode(), actual)

    def test_unapproved_app_refused(self):
        (self.source / "Apps/rogue").mkdir()
        with self.assertRaises(ValueError):
            build(self.source, self.selection, self.root / "homedock")
        self.assertFalse((self.root / "homedock").exists())


if __name__ == "__main__":
    unittest.main()
