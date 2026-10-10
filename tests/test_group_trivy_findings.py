import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from group_trivy_findings import aggregate, markdown

class GroupTrivyTests(unittest.TestCase):
    def setUp(self):
        self.usage={"example:1":["AppA","AppB"],"example:2":["AppC"]}
        self.expected={"example:1":["amd64","arm64"],"example:2":["amd64","arm64"]}
        self.hit={"cve":"CVE-2026-1234","package":"openssl","severity":"HIGH",
                  "installed":"1.0","fixed":"1.1","target":"alpine"}
        self.runs=[{"results":[
            {"image":image,"status":"vulnerable","scans":{
                arch:{"status":"ok","critical":0,"high":1,"findings":[self.hit]}
                for arch in ["amd64","arm64"]}}
            for image in self.expected]}]

    def test_cross_app_group_by_dependency_and_cve(self):
        report=aggregate(self.runs,self.usage,self.expected)
        self.assertEqual(len(report["groups"]),1)
        self.assertEqual(report["groups"][0]["apps"],["AppA","AppB","AppC"])
        self.assertEqual(report["groups"][0]["platforms"],["amd64","arm64"])
        self.assertEqual(len(report["groups"][0]["occurrences"]),4)
        self.assertEqual(report["high"],4)
        self.assertFalse(report["incomplete"])
        self.assertIn("AppA",markdown(report))

    def test_individual_app_statuses_reflect_shared_images(self):
        report = aggregate(self.runs, self.usage, self.expected)
        self.assertEqual(report["applications_summary"],
                         {"not_verified": 0, "vulnerable": 3,
                          "no_high_critical_detected": 0})
        self.assertEqual([item["app"] for item in report["applications"]],
                         ["AppA", "AppB", "AppC"])
        self.assertEqual(report["applications"][0]["high"], 2)
        self.assertIn("| AppA | VULNERABLE |", markdown(report))

    def test_complete_zero_findings_is_not_mistaken_for_missing_evidence(self):
        clean = [{"results": [
            {"image": image, "status": "clean", "scans": {
                arch: {"status": "ok", "critical": 0, "high": 0, "findings": []}
                for arch in ("amd64", "arm64")}}
            for image in self.expected]}]
        report = aggregate(clean, self.usage, self.expected)
        self.assertEqual(report["applications_summary"]["no_high_critical_detected"], 3)
        self.assertEqual(report["applications_summary"]["not_verified"], 0)

    def test_missing_architecture_never_clean(self):
        broken=[{"results":[{"image":"example:1","status":"clean",
                 "scans":{"amd64":{"status":"ok","findings":[],"high":0,"critical":0}}}]}]
        report=aggregate(broken,self.usage,self.expected)
        self.assertEqual(report["missing_images"],["example:2"])
        self.assertEqual(report["incomplete"][0]["issues"][0]["platform"],"arm64")
        self.assertEqual(report["applications_summary"]["not_verified"], 3)
        self.assertTrue(all(app["status"] == "not_verified"
                            for app in report["applications"]))

    def test_missing_package_evidence_never_clean(self):
        old=[{"results":[{"image":"example:1","status":"clean",
              "scans":{arch:{"status":"ok","high":0,"critical":0} for arch in ["amd64","arm64"]}}]}]
        report=aggregate(old,self.usage,self.expected)
        self.assertEqual(len(report["incomplete"][0]["issues"]),2)
        self.assertEqual(report["applications_summary"]["not_verified"], 3)

if __name__=="__main__":
    unittest.main()
