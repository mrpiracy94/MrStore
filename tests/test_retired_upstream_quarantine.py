"""Release quarantine must not silently publish officially retired images.

Checks an explicit release policy decision independently of changing CVE reports.
Does not install images or weaken the zero-HIGH/CRITICAL gate.
"""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import apps
from image_freshness import RETIRED_UPSTREAM
from release_catalog import insecure_defaults


class RetiredImageSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_name = {entry.folder: entry for entry in apps()}

    def test_officially_discontinued_steamos_is_blocked(self):
        entry = self.by_name["steamos"]
        ref = entry.source["services"]["steamos"]["image"]
        self.assertEqual(ref, "lscr.io/linuxserver/steamos:latest")
        self.assertIn(ref, RETIRED_UPSTREAM)
        reasons = insecure_defaults(entry)
        self.assertTrue(any("discontinued upstream image" in reason
                            and ref in reason for reason in reasons), reasons)

    def test_source_inventory_retains_discontinued_entry_for_review(self):
        self.assertEqual(len(self.by_name), 254)
        self.assertIn("steamos", self.by_name)

    def test_other_images_are_not_blanket_blocklisted(self):
        app = self.by_name["actual-budget"]
        self.assertNotIn(app.source["services"]["actual-budget"]["image"], RETIRED_UPSTREAM)
        self.assertFalse(any("discontinued upstream image" in reason
                             for reason in insecure_defaults(app)))


if __name__ == "__main__":
    unittest.main()
