"""All published source manifests must retain reviewed immutable digests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_source_digests import inspect

A = "sha256:" + "a" * 64
B = "sha256:" + "b" * 64


class SourceDigestGateTests(unittest.TestCase):
    def make_root(self, tmp, image, expected=None):
        root = Path(tmp)
        (root / "data").mkdir()
        (root / "Apps/test").mkdir(parents=True)
        (root / "Apps/test/docker-compose.yml").write_text(
            f"services:\n  test:\n    image: {image}\n", encoding="utf-8")
        (root / "data/image-digests.json").write_text(json.dumps({
            "images": {"example:1": expected if expected is not None else A}
        }), encoding="utf-8")
        return root

    def test_exact_pinned_source_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspect(self.make_root(d, "example:1@" + A))
            self.assertEqual((result["apps"], result["service_images"], result["problems"]),
                             (1, 1, []))

    def test_mutable_source_is_rejected_even_with_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspect(self.make_root(d, "example:1"))
            self.assertIn("mutable image", result["problems"][0])

    def test_wrong_digest_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspect(self.make_root(d, "example:1@" + B))
            self.assertIn("differs", result["problems"][0])

    def test_missing_baseline_entry_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.make_root(d, "example:1@" + A)
            (root / "data/image-digests.json").write_text('{"images":{}}')
            self.assertIn("missing or invalid", inspect(root)["problems"][0])

    def test_every_real_app_and_image_pinned(self):
        report = inspect(ROOT)
        self.assertEqual(report["apps"], 254)
        self.assertGreaterEqual(report["service_images"], 254)
        self.assertEqual(report["problems"], [])


if __name__ == "__main__":
    unittest.main()
