"""Offline checks for issue #64; candidate comparisons never deploy."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from catalog import apps
from maintenance_candidates import CANDIDATES, compare


class MaintenanceCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_name = {item.folder: item for item in apps()}

    def test_stale_apps_are_listed_not_automatically_replaced(self):
        self.assertEqual(set(CANDIDATES), {"organizr", "series-troxide", "dockge"})
        self.assertEqual(CANDIDATES["series-troxide"], [])
        self.assertTrue(all(name in self.by_name for name in CANDIDATES))

    def test_clean_scan_never_approves_untrusted_fork(self):
        queried = []
        def resolver(image):
            return image + "@sha256:" + "a" * 64, None
        def scanner(image, *, platform):
            queried.append((image, platform))
            return [], None
        report = compare(self.by_name["organizr"], resolver, scanner)
        self.assertEqual(len(report["evidence"]), 3)
        self.assertEqual({p for _, p in queried}, {"amd64", "arm64"})
        self.assertEqual(len(queried), 6)
        self.assertTrue(all(x["scan_result"] == "no_high_or_critical_detected"
                            for x in report["evidence"]))
        self.assertFalse(report["any_automatically_approved"])
        self.assertFalse(report["catalog_mutated"])
        self.assertTrue(all(not x["automatically_approved"] and
                            not x["trusted_source_verified"]
                            for x in report["evidence"]))

    def test_arm64_high_is_not_clean(self):
        def resolver(image):
            return image + "@sha256:" + "b" * 64, None
        def scanner(image, *, platform):
            return ([{"severity": "HIGH"}] if platform == "arm64" else []), None
        report = compare(self.by_name["dockge"], resolver, scanner)
        self.assertEqual(len(report["evidence"]), 2)
        self.assertTrue(all(x["scan_result"] == "vulnerable"
                            for x in report["evidence"]))

    def test_registry_and_scanner_errors_are_inconclusive(self):
        def resolver(image):
            return None, "429"
        report = compare(self.by_name["series-troxide"], resolver,
                         lambda *_a, **_kw: self.fail("scanner must not be called"))
        self.assertEqual(report["evidence"][0]["scan_result"], "inconclusive")
        def resolver2(image):
            return image + "@sha256:" + "c" * 64, None
        def failing(*_args, **_kwargs):
            raise RuntimeError("scanner down")
        report = compare(self.by_name["series-troxide"], resolver2, failing)
        self.assertEqual(report["evidence"][0]["scan_result"], "inconclusive")
        self.assertTrue(all(x["status"] == "error" for x in
                            report["evidence"][0]["scans"].values()))


if __name__ == "__main__":
    unittest.main()
