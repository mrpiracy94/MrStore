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

    def test_discontinued_steamos_remains_blocklisted_and_absent(self):
        # Removed deliberately from the active source on 2026-10-10.
        # Do not reintroduce unsupported SteamOS just to restore a count.
        ref = "lscr.io/linuxserver/steamos:latest"
        self.assertIn(ref, RETIRED_UPSTREAM)
        self.assertNotIn("steamos", self.by_name)

    def test_active_inventory_is_253_after_steamos_retirement(self):
        self.assertEqual(len(self.by_name), 253)
        self.assertNotIn("steamos", self.by_name)

    def test_other_images_are_not_blanket_blocklisted(self):
        app = self.by_name["actual-budget"]
        self.assertNotIn(app.source["services"]["actual-budget"]["image"], RETIRED_UPSTREAM)
        self.assertFalse(any("discontinued upstream image" in reason
                             for reason in insecure_defaults(app)))


if __name__ == "__main__":
    unittest.main()
