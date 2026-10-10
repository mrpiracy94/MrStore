"""Regression tests for fast per-application CVE audits (fully offline)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cves import (application_results, changed_apps_since, evaluate,
                  scan, select_app_images)


class FastAppAuditTests(unittest.TestCase):
    def test_app_selection_deduplicates_shared_images(self):
        usage = {
            "demo/server:1": ["alpha/web", "beta/web"],
            "demo/db:2": ["alpha/db"],
            "demo/third:1": ["gamma/web"],
        }
        self.assertEqual(select_app_images(usage, {"alpha"}),
                         ["demo/db:2", "demo/server:1"])
        self.assertEqual(select_app_images(usage, {"alpha", "beta"}),
                         ["demo/db:2", "demo/server:1"])
        with self.assertRaises(ValueError):
            select_app_images(usage, {"missing"})

    def test_only_apps_changed_in_git_diff_are_selected(self):
        base = "a" * 40
        change_list = ("Apps/alpha/docker-compose.yml\0"
                       "Apps/beta/icons/icon.png\0"
                       "README.md\0")
        result = subprocess.CompletedProcess(["git"], 0, change_list, "")
        with patch("cves.subprocess.run", return_value=result) as runner:
            selected = changed_apps_since(ROOT, base)
        self.assertEqual(selected, {"alpha", "beta"})
        args = runner.call_args.args[0]
        self.assertEqual(args[-3:], ["HEAD", "--", "Apps/"])
        self.assertIn("-z", args)

    def test_invalid_change_baseline_is_not_a_clean_scan(self):
        with self.assertRaises(ValueError):
            changed_apps_since(ROOT, "not-a-commit")

    def test_parallel_results_keep_image_order(self):
        barrier = threading.Barrier(2)

        def scanner(image):
            barrier.wait(timeout=5)
            return [], None

        usage = {"example/one:1": ["one/app"],
                 "example/two:2": ["two/app"]}
        images = ["example/two:2", "example/one:1"]
        report = evaluate(usage, images, scanner=scanner, workers=2)
        self.assertEqual([x["image"] for x in report["results"]], images)
        self.assertEqual(report["failures"], 0)
        self.assertEqual(report["applications"]["one"]["status"],
                         "no_high_critical_detected")

    def test_partial_or_failed_app_cannot_be_marked_clean(self):
        usage = {"example/a:1": ["demo/web"],
                 "example/b:2": ["demo/db"]}
        clean = [{"image": "example/a:1", "status": "ok", "findings": []}]
        status = application_results(usage, clean)["demo"]
        self.assertEqual(status["status"], "partial")
        self.assertFalse(status["complete"])

        failure = clean + [{"image": "example/b:2", "status": "error",
                            "error": "registry 429", "findings": []}]
        status = application_results(usage, failure)["demo"]
        self.assertEqual(status["status"], "inconclusive")
        self.assertTrue(status["complete"])

    def test_findings_cannot_be_hidden_by_incomplete_app_scan(self):
        usage = {"example/a:1": ["demo/web"],
                 "example/b:2": ["demo/db"]}
        finding = {"severity": "CRITICAL", "cve": "CVE-TEST"}
        status = application_results(usage, [
            {"image": "example/a:1", "status": "ok", "findings": [finding]}
        ])["demo"]
        self.assertEqual(status["status"], "vulnerable")
        self.assertEqual(status["critical"], 1)
        self.assertFalse(status["complete"])

    def test_daily_scan_is_configured_for_126_simultaneous_images(self):
        import yaml
        workflow = yaml.load(
            (ROOT / ".github/workflows/cve-scan.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        job = workflow["jobs"]["trivy"]
        self.assertEqual(job["strategy"]["max-parallel"], "32")
        self.assertIn(",".join(str(i) for i in range(32)), job["strategy"]["matrix"]["shard"])
        command = next(step["run"] for step in job["steps"]
                       if step.get("name") == "Scan image shard for critical CVEs")
        self.assertIn('--shards 32 --shard "$SHARD" --workers "$workers"', command)
        self.assertIn('if [ "$SHARD" = \'31\' ]; then workers=2; fi', command)
        self.assertEqual((int(job["strategy"]["max-parallel"]) - 1) * 4 + 2, 126)

    def test_release_audit_is_configured_for_126_simultaneous_images(self):
        import yaml
        workflow = yaml.load(
            (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        job = workflow["jobs"]["security_audit"]
        self.assertEqual(job["strategy"]["max-parallel"], "32")
        self.assertEqual(len(job["strategy"]["matrix"]["shard"]), 32)
        command = next(step["run"] for step in job["steps"]
                       if step.get("name") ==
                       "Scan all catalog images by immutable digest on AMD64 and ARM64")
        self.assertIn('--workers "$workers"', command)
        self.assertIn('if [ "${{ matrix.shard }}" = \'31\' ]; then workers=2; fi', command)
        self.assertEqual((int(job["strategy"]["max-parallel"]) - 1) * 4 + 2, 126)

    def test_release_parallel_checks_preserve_every_architecture_and_status(self):
        from catalog import App
        from release_scan import audit_shard

        barrier = threading.Barrier(4)
        items = []
        for i in range(4):
            folder = f"app{i}"
            items.append(App(
                folder, ROOT / "Apps" / folder / "docker-compose.yml",
                {"services": {"web": {"image": f"example/demo{i}:1"}}},
                {"architectures": ["amd64", "arm64"]}))

        def resolve(image):
            barrier.wait(timeout=5)
            return image + "@sha256:" + "a" * 64, None

        def scanner(image, platform):
            return ([{"severity": "HIGH", "package": "demo",
                      "cve": "CVE-TEST", "installed": "1", "fixed": "2"}]
                    if image.startswith("example/demo2:") and platform == "arm64"
                    else []), None

        report = audit_shard(items, 0, 1, resolver=resolve,
                             scanner=scanner, workers=4)
        self.assertEqual(len(report["results"]), 4)
        self.assertEqual([result["image"] for result in report["results"]],
                         [f"example/demo{i}:1" for i in range(4)])
        self.assertEqual(
            [result["status"] for result in report["results"]],
            ["clean", "clean", "vulnerable", "clean"])
        self.assertTrue(all(set(result["scans"]) == {"amd64", "arm64"}
                            for result in report["results"]))

    def test_32_way_partition_is_complete_and_disjoint(self):
        from cves import shard_images
        refs = [f"example/app{i}:1" for i in range(258)]
        groups = [shard_images(refs, i, 32) for i in range(32)]
        self.assertEqual(sorted([item for group in groups for item in group]),
                         sorted(refs))
        self.assertTrue(all(len(group) > 0 for group in groups))

    def test_release_compiles_crane_once_not_per_shard(self):
        import yaml
        workflow = yaml.load(
            (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        jobs = workflow["jobs"]
        self.assertEqual(jobs["security_audit"]["needs"], ["preflight", "prepare_crane"])
        prepare = " ".join(str(s.get("run", "")) for s in jobs["prepare_crane"]["steps"])
        scan = " ".join(str(s.get("run", "")) for s in jobs["security_audit"]["steps"])
        self.assertIn("go install github.com/google/go-containerregistry/cmd/crane@v0.21.7", prepare)
        self.assertNotIn("go install", scan)
        self.assertTrue(any(s.get("uses") == "actions/download-artifact@v8"
                            and s.get("with", {}).get("name") == "mrstore-pinned-crane"
                            for s in jobs["security_audit"]["steps"]))

    def test_release_does_not_repeat_preflight_tests_after_scan(self):
        import yaml
        workflow = yaml.load(
            (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        jobs = workflow["jobs"]
        preflight = jobs["preflight"]["steps"]
        self.assertTrue(any("python -m unittest discover -s tests -v" in s.get("run", "")
                            and s.get("if") == "github.event_name != 'pull_request'"
                            for s in preflight))
        build = jobs["build"]["steps"]
        self.assertFalse(any("python -m unittest" in s.get("run", "")
                             for s in build))

    def test_126_capacity_stress_does_not_run_on_every_pr_edit(self):
        import yaml
        workflow = yaml.load(
            (ROOT / ".github/workflows/cve-capacity-validation.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(list(workflow["on"]), ["workflow_dispatch"])
        self.assertEqual(workflow["jobs"]["scan"]["strategy"]["max-parallel"], "32")

    def test_inconclusive_recheck_has_bounded_parallelism_and_no_stale_pr_runs(self):
        import yaml
        workflow = yaml.load(
            (ROOT / ".github/workflows/retry-inconclusive-cves.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(workflow["jobs"]["rescan"]["strategy"]["max-parallel"], "4")
        step = next(s for s in workflow["jobs"]["rescan"]["steps"]
                    if s.get("id") == "scan")
        self.assertIn("--workers 4", step["run"])
        self.assertEqual(step["env"]["MRSTORE_CVE_DB_PREPARED"], "1")
        self.assertIn("pull_request", workflow["concurrency"]["cancel-in-progress"])

    def test_parallel_trivy_uses_memory_cache_only_when_db_is_prepared(self):
        done = subprocess.CompletedProcess(["trivy"], 0, json.dumps(
            {"Results": [{"Target": "example/app:1", "Vulnerabilities": []}]}), "")
        with patch.dict(os.environ, {"MRSTORE_CVE_DB_PREPARED": "1"}), \
             patch("cves.subprocess.run", return_value=done) as runner:
            self.assertEqual(scan("example/app:1"), ([], None))
        args = runner.call_args.args[0]
        for flag in ("--cache-backend", "memory", "--skip-db-update",
                     "--skip-java-db-update"):
            self.assertIn(flag, args)
        # Four subprocesses per small hosted runner must not double their own
        # internal parallelism and exhaust CPU or memory.
        self.assertEqual(args[args.index("--parallel") + 1], "1")


if __name__ == "__main__":
    unittest.main()
