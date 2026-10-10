"""Regression checks for non-security MrStore storefront data."""
from pathlib import Path
import unittest

from scripts.branding_report import ROOT, SUPPORTED, audit


class BrandingTests(unittest.TestCase):
    def test_storefront_data_is_consistent(self):
        data = audit(ROOT)
        self.assertEqual([], data["errors"])
        self.assertEqual(9, data["categories"])
        self.assertGreaterEqual(data["recommended"], 10)
        self.assertGreaterEqual(data["featured"], 5)

    def test_pt_app_descriptions_are_populated(self):
        data = audit(ROOT)
        self.assertGreaterEqual(data["descriptions_pt_PT"], 15)

    def test_authentic_upstream_screenshots_are_present(self):
        data = audit(ROOT)
        self.assertGreaterEqual(data["local_screenshots"], 3)


if __name__ == "__main__":
    unittest.main()
