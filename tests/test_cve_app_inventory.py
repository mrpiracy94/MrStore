"""Offline per-application CVE report tests: never infer clean from missing scans."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cves import shard_images
from cve_app_inventory import inspect_shard, load_evidence, make_report, output_report


class CVEAppInventoryTests(unittest.TestCase):
    images = {
        "example/clean@sha256:" + "a"*64: ["clean/primary"],
        "example/vuln:stable": ["vulnerable/primary"],
    }

    def reports(self, image_status="vulnerable", skip=None):
        results = {}
        platforms = {name: ["amd64"] for name in self.images}
        for shard in range(8):
            chosen = shard_images(self.images, shard, 8)
            rows = []
            for image in chosen:
                is_vulnerable = image.endswith(":stable")
                status = image_status if is_vulnerable else "clean"
                rows.append({
                    "image": image,
                    "status": status,
                    "error": None,
                    "pinned": image if "@sha256:" in image else image + "@sha256:" + "b"*64,
                    "platforms": ["amd64"],
                    "scans": {"amd64": {
                        "status": "ok", "error": None,
                        "critical": 1 if is_vulnerable else 0,
                        "high": 2 if is_vulnerable else 0,
                        "findings": [{"cve": "CVE-2026-1234", "severity": "HIGH"}]
                        if is_vulnerable else []
                    }}
                })
            results[shard] = {
                "shard": shard, "shards": 8,
                "images_total": 2, "images_checked": len(rows),
                "results": rows
            }
        return results, platforms

    def test_one_vulnerable_one_clean(self):
        reports, platforms = self.reports()
        merged = {}
        for i in range(8):
            merged.update(inspect_shard(reports[i], i, self.images, platforms))
        entries = [SimpleNamespace(folder=name, source={
            "services": {"primary": {"image": image}}})
                   for image, uses in self.images.items()
                   for name in [uses[0].split("/")[0]]]
        output = make_report(entries, merged, [], "test-sha")
        self.assertEqual([r["app"] for r in output["apps"]], ["clean", "vulnerable"])
        self.assertEqual([r["status"] for r in output["apps"]],
                         ["CLEAN_IN_AVAILABLE_EVIDENCE", "CVE_DETECTED"])
        self.assertEqual(output["apps"][1]["cves"], ["CVE-2026-1234"])
        self.assertFalse(any(r["final_release_approved"] for r in output["apps"]))

    def test_missing_shard_always_pending(self):
        reports, platforms = self.reports()
        with TemporaryDirectory() as folder:
            for shard, item in reports.items():
                if item["results"]:  # omit whichever shard contains an image
                    continue
                (Path(folder) / f"release-cves-shard-{shard}.json").write_text(
                    json.dumps(item), encoding="utf-8")
            evidence, warnings = load_evidence(Path(folder), self.images, platforms)
            self.assertTrue(warnings)
            self.assertEqual(evidence, {})

    def test_bad_clean_label_is_not_trusted(self):
        reports, platforms = self.reports(image_status="clean")
        candidate = next((i for i, x in reports.items() if
                          any(r["image"].endswith(":stable") for r in x["results"])))
        with self.assertRaisesRegex(ValueError, "Contradictory"):
            inspect_shard(reports[candidate], candidate, self.images, platforms)

    def test_duplicate_images_fail_entire_shard(self):
        reports, platforms = self.reports()
        candidate = next(i for i, x in reports.items() if x["results"])
        reports[candidate]["results"].append(reports[candidate]["results"][0])
        reports[candidate]["images_checked"] += 1
        with self.assertRaisesRegex(ValueError, "duplicate"):
            inspect_shard(reports[candidate], candidate, self.images, platforms)

    def test_reports_are_alphabetical_and_exported(self):
        sample = [SimpleNamespace(folder="zeta", source={
            "services": {"svc": {"image": "unknown/ref:1"}}}),
                  SimpleNamespace(folder="alfa", source={
            "services": {"svc": {"image": "unknown/ref:1"}}})]
        result = make_report(sample, {}, ["all shards missing"])
        self.assertEqual([r["app"] for r in result["apps"]], ["alfa", "zeta"])
        self.assertEqual(result["app_status_counts"]["PENDING_EVIDENCE"], 2)
        with TemporaryDirectory() as folder:
            output_report(result, Path(folder))
            self.assertTrue((Path(folder) / "cve-apps.json").is_file())
            self.assertEqual((Path(folder) / "cve-apps.csv").read_bytes()[:3],
                             b"\xef\xbb\xbf")
            self.assertIn("zeta", (Path(folder) / "cve-apps.md").read_text())


if __name__ == "__main__":
    unittest.main()
