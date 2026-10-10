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

    def test_missing_architecture_never_clean(self):
        broken=[{"results":[{"image":"example:1","status":"clean",
                 "scans":{"amd64":{"status":"ok","findings":[],"high":0,"critical":0}}}]}]
        report=aggregate(broken,self.usage,self.expected)
        self.assertEqual(report["missing_images"],["example:2"])
        self.assertEqual(report["incomplete"][0]["issues"][0]["platform"],"arm64")

    def test_missing_package_evidence_never_clean(self):
        old=[{"results":[{"image":"example:1","status":"clean",
              "scans":{arch:{"status":"ok","high":0,"critical":0} for arch in ["amd64","arm64"]}}]}]
        report=aggregate(old,self.usage,self.expected)
        self.assertEqual(len(report["incomplete"][0]["issues"]),2)

if __name__=="__main__":
    unittest.main()
