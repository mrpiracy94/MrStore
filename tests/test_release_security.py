"""Offline checks for per-architecture release approval and Docker privilege policy."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog import App, apps, image_usage
from cves import shard_images
from privilege_policy import regressions, risky_settings
from quarantine import decide, main as quarantine_main
from release_security import audit, declared_platforms


class SecurityReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name, image, risky in (
            ("clean", "example/clean:v1", False),
            ("vulnerable", "example/vulnerable:v1", False),
            ("elevated", "example/elevated:v1", True),
        ):
            folder = self.root / "Apps" / name
            folder.mkdir(parents=True)
            doc = {
                "services": {"web": {"image": image, **({"privileged": True} if risky else {})}},
                "x-casaos": {"architectures": ["amd64", "arm64"]},
            }
            (folder / "docker-compose.yml").write_text(yaml.safe_dump(doc))

        self.reports = self.root / "scans"
        self.reports.mkdir()
        items = apps(self.root)
        self.usage = image_usage(items)
        self.platforms = declared_platforms(items)
        self.digest = "sha256:" + "a" * 64
        for shard in range(8):
            chosen = shard_images(self.usage, shard, 8)
            rows = audit(self.usage, self.platforms, chosen,
                         scanner=self.fake_scan,
                         resolver=lambda image: (self.digest, None))
            (self.reports / f"release-security-{shard}.json").write_text(json.dumps({
                "schema": 1, "shard": shard, "shards": 8,
                "images_total": len(self.usage), "results": rows,
            }))

    @staticmethod
    def fake_scan(pinned, platform):
        if "vulnerable" in pinned and platform == "linux/arm64":
            return ([{"severity": "HIGH", "cve": "CVE-TEST", "package": "lib"}], None)
        return [], None

    def test_all_architectures_are_scanned_with_digest(self):
        image = "example/clean:v1"
        results = audit({image: ["clean/web"]}, {image: ["amd64", "arm64"]},
                        [image], scanner=self.fake_scan,
                        resolver=lambda _: (self.digest, None))
        row = results[0]
        self.assertEqual(row["pinned"], image + "@" + self.digest)
        self.assertEqual([c["arch"] for c in row["checks"]], ["amd64", "arm64"])
        self.assertTrue(all(c["status"] == "ok" for c in row["checks"]))

    def test_unavailable_digest_quarantines_without_scanning(self):
        image = "example/broken:v1"
        def impossible_scan(*args, **kwargs):
            self.fail("scan must not run if the manifest digest is unknown")
        results = audit({image: ["a/b"]}, {image: ["amd64", "arm64"]},
                        [image], scanner=impossible_scan,
                        resolver=lambda _: (None, "registry timeout"))
        self.assertIsNone(results[0]["pinned"])
        self.assertEqual([c["status"] for c in results[0]["checks"]],
                         ["error", "error"])

    def test_unsafe_or_arm64_vulnerable_apps_are_excluded(self):
        outcome = decide(self.root, sorted(self.reports.glob("*.json")))
        self.assertEqual(outcome["approved_apps"], ["clean"])
        self.assertIn("vulnerable", outcome["quarantined_apps"])
        self.assertIn("elevated", outcome["quarantined_apps"])
        self.assertIn("arm64", str(outcome["quarantined_apps"]["vulnerable"]))
        self.assertEqual(outcome["pinned_images"]["example/clean:v1"],
                         "example/clean:v1@" + self.digest)

    def test_reject_missing_scan_group(self):
        files = sorted(self.reports.glob("*.json"))[:-1]
        with self.assertRaisesRegex(ValueError, "Expected 8"):
            decide(self.root, files)

    def test_reject_missing_arm64_check_even_if_amd64_is_clean(self):
        path = self.reports / "release-security-0.json"
        report = json.loads(path.read_text())
        if not report["results"]:
            self.skipTest("Unexpected empty fixture shard")
        report["results"][0]["checks"] = report["results"][0]["checks"][:1]
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "architecture check"):
            decide(self.root, sorted(self.reports.glob("*.json")))

    def test_apply_only_filters_runner_checkout_and_pins_approved(self):
        before = (self.root / "Apps" / "clean" / "docker-compose.yml").read_text()
        args = [
            "quarantine.py", "--root", str(self.root),
            "--reports-dir", str(self.reports),
            "--output", str(self.root / "quarantine.json"),
            "--summary", str(self.root / "quarantine.md"), "--apply",
        ]
        with patch.object(sys, "argv", args):
            self.assertEqual(quarantine_main(), 0)
        self.assertFalse((self.root / "Apps" / "vulnerable").exists())
        self.assertFalse((self.root / "Apps" / "elevated").exists())
        updated = (self.root / "Apps" / "clean" / "docker-compose.yml").read_text()
        self.assertNotEqual(updated, before)
        self.assertEqual(yaml.safe_load(updated)["services"]["web"]["image"],
                         "example/clean:v1@" + self.digest)

    def test_blocks_privileged_and_docker_socket_additions(self):
        doc = {"services": {"web": {"privileged": True, "cap_add": ["SYS_ADMIN"],
                                    "volumes": ["/var/run/docker.sock:/var/run/docker.sock"]}}}
        names = {entry[1] for entry in risky_settings(doc)}
        self.assertEqual(names, {"privileged", "cap_add", "sensitive_mount"})
        current = [App("new", Path("new"), doc, {})]
        self.assertEqual(len(regressions(current, {})), 3)
        self.assertEqual(regressions(current, {"new": risky_settings(doc)}), [])

    def test_malicious_platform_is_never_silently_scanned_as_native(self):
        from cves import scan
        with self.assertRaisesRegex(ValueError, "Invalid platform"):
            scan("example/foo:bar", platform="windows/amd64")


if __name__ == "__main__":
    unittest.main()
