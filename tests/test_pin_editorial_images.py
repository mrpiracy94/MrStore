"""Regressoes offline: integridade das imagens Docker do catalogo editorial."""
from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pin_editorial_images", ROOT / "scripts/pin_editorial_images.py")
pin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin)
A = "sha256:" + "a" * 64
B = "sha256:" + "b" * 64


class PinEditorialImagesTest(unittest.TestCase):
    def test_preserves_metadata(self):
        text = ("services:\n  main:\n    image: example/app:latest\n    ports:\n"
                "      - '8080:80'\nx-casaos:\n  id: test.store\n")
        result, n = pin.pin_text(text, {"example/app:latest": A})
        parsed = yaml.safe_load(result)
        self.assertEqual(n, 1)
        self.assertEqual(parsed["x-casaos"]["id"], "test.store")
        self.assertEqual(parsed["services"]["main"]["ports"], ["8080:80"])
        self.assertEqual(parsed["services"]["main"]["image"], "example/app:latest@" + A)

    def test_missing_digest_blocks(self):
        with self.assertRaises(pin.PinError):
            pin.pin_text("services:\n  x:\n    image: example/app:latest\n", {})

    def test_corrupt_digest_blocks(self):
        with self.assertRaises(pin.PinError):
            pin.pin_text("services:\n  x:\n    image: example/app:latest\n", {"example/app:latest": "sha256:invalid"})

    def test_pinned_ref_matches_unpinned_baseline(self):
        result, n = pin.pin_text("services:\n  x:\n    image: example/app:latest@" + A + "\n",
                                 {"example/app:latest": A})
        self.assertEqual(n, 1)
        self.assertIn("example/app:latest@" + A, result)

    def test_mismatched_digest_blocks(self):
        with self.assertRaises(pin.PinError):
            pin.pin_text("services:\n  x:\n    image: example/app:latest@" + A + "\n",
                         {"example/app:latest": B})

    def test_stage_atomic_on_missing_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, image in (("a", "example/a:1"), ("b", "example/b:1")):
                path = root / "Apps" / name / "docker-compose.yml"
                path.parent.mkdir(parents=True)
                path.write_text("services:\n  x:\n    image: " + image + "\n")
            first = root / "Apps/a/docker-compose.yml"
            with self.assertRaises(pin.PinError):
                pin.pin_stage(root, {"images": {"example/a:1": A}})
            self.assertNotIn("@sha256:", first.read_text())

    def test_stage_success(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Apps/a/docker-compose.yml"
            p.parent.mkdir(parents=True)
            p.write_text("services:\n  x:\n    image: example/a:1\n")
            self.assertEqual(pin.pin_stage(Path(d), {"images": {"example/a:1": A}}), (1, 1))
            self.assertIn("example/a:1@" + A, p.read_text())


if __name__ == "__main__":
    unittest.main()
