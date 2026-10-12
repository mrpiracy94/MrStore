"""Offline, deterministic tests for scanning all MrStore images for CVE reductions."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cve_remediation_sweep as sweep
from catalog import apps, image_usage
from cves import shard_images

TAG = "lscr.io/linuxserver/grocy:latest"
NEW = "sha256:" + "b" * 64

class ContinuousRemediationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads((ROOT / "data/image-digests.json").read_text())
        cls.old = cls.baseline["images"][TAG]
        cls.usage = image_usage(apps(ROOT))

    def resolver(self, tag):
        return (NEW if tag == TAG else self.baseline["images"].get(tag), None)

    def test_full_catalog_covered_in_eight_disjoint_shards(self):
        self.assertEqual(len(apps(ROOT)), 254)
        self.assertEqual(len(self.usage), 258)
        shards = [set(shard_images(self.usage, shard, 8)) for shard in range(8)]
        self.assertEqual(set.union(*shards), set(self.usage))
        self.assertEqual(sum(len(x) for x in shards), len(self.usage))

    def test_changed_digest_scanned_only_on_declared_architectures(self):
        calls = []
        def scanner(image, arch):
            calls.append((image, arch))
            return {"critical": 0, "high": 0 if "@" + NEW in image else 9}
        result = sweep.inspect(ROOT, shard=0, shards=1, resolver=self.resolver,
                               scanner=scanner)
        self.assertTrue(result["complete"])
        self.assertEqual(result["source_app_count"], 254)
        self.assertEqual(result["all_images"], 258)
        self.assertEqual(result["changed_images"], 1)
        self.assertEqual(len(result["comparisons"]), 1)
        outcome = result["comparisons"][0]
        self.assertEqual(outcome["app"], "grocy")
        self.assertEqual(outcome["result"], "lower_observed_cves")
        self.assertFalse(outcome["automatic_update_allowed"])
        self.assertEqual(len(calls), 4)
        self.assertEqual(set(arch for _, arch in calls), {"amd64", "arm64"})

    def test_registry_failure_remains_inconclusive(self):
        def failing(tag):
            return (None, "429") if tag == TAG else (self.baseline["images"].get(tag), None)
        report = sweep.inspect(ROOT, shard=0, shards=1, resolver=failing,
                               scanner=lambda *args: self.fail("unchanged must not scan"))
        self.assertFalse(report["complete"])
        self.assertEqual(report["changed_images"], 0)
        self.assertEqual(len(report["registry_errors"]), 1)

    def test_trivy_failure_remains_inconclusive(self):
        def scanner(image, arch):
            if "@" + NEW in image and arch == "arm64":
                raise RuntimeError("TOOMANYREQUESTS")
            return {"critical": 0, "high": 9}
        report = sweep.inspect(ROOT, shard=0, shards=1, resolver=self.resolver,
                               scanner=scanner)
        self.assertFalse(report["complete"])
        self.assertEqual(report["comparisons"][0]["result"], "inconclusive")

    def test_scan_failures_not_counted_as_zero(self):
        with patch.object(sweep, "scan", return_value=([], "Trivy scan error")):
            with self.assertRaisesRegex(RuntimeError, "Trivy scan error"):
                sweep.count_cves("example:1", "amd64")

if __name__ == "__main__":
    unittest.main()
