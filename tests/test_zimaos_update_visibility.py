"""Offline regression tests for non-invasive ZimaOS update diagnostics."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from zimaos_update_visibility import (
    catalog_item, compare_digests, docker_repo_digests, is_latest,
    native_upgradable, runtime_check, scan_catalog, validate_api_base,
)
from catalog import App


def fixture(name="test-app", service="web", container="web", image="example/app:latest"):
    spec = {"image": image}
    if container is not None:
        spec["container_name"] = container
    document = {"name": name, "services": {service: spec},
                "x-casaos": {"id": "io.github.mrpiracy94." + name, "main": service,
                             "version": "1.0.0"}}
    return App(name, Path("Apps") / name / "docker-compose.yml",
               document, document["x-casaos"])


def fake_run_for(values):
    def fake(command, **kwargs):
        joined = " ".join(command)
        for text, output in values.items():
            if text in joined:
                return subprocess.CompletedProcess(command, 0, output, "")
        return subprocess.CompletedProcess(command, 1, "", "no match")
    return fake


class UpdateVisibilityTests(unittest.TestCase):
    def test_latest_detected_on_pinned_tag(self):
        self.assertTrue(is_latest("linuxserver/sonarr:latest@sha256:" + "a" * 64))
        self.assertFalse(is_latest("ghcr.io/immich/server:release"))
        self.assertFalse(is_latest("repo/foo@sha256:" + "a" * 64))

    def test_static_flags_mismatched_main_container(self):
        report = catalog_item(fixture(service="app", container="my-app"))
        self.assertIn("main_container_name_differs_from_service", report["findings"])
        self.assertIn("latest_requires_usable_local_repodigest", report["findings"])

    def test_static_flags_implicit_compose_container_name(self):
        report = catalog_item(fixture(service="app", container=None))
        self.assertIn("main_container_name_not_explicit", report["findings"])

    def test_matching_main_container_avoids_592_warning(self):
        report = catalog_item(fixture(image="registry/demo:1.2.3"))
        self.assertEqual(report["findings"], [])

    def test_registry_digest_is_only_evidence_when_available(self):
        a = "sha256:" + "a" * 64
        b = "sha256:" + "b" * 64
        self.assertEqual(compare_digests(["demo@" + a], a), "digest_matches")
        self.assertEqual(compare_digests(["demo@" + a], b), "digest_differs_review_required")
        self.assertEqual(compare_digests([], b), "unknown_missing_repodigests")
        self.assertEqual(compare_digests(None, b), "unknown_local_inspection_failed")
        self.assertEqual(compare_digests(["demo@" + a], None), "unknown_remote_not_checked")

    def test_docker_digest_probe_avoids_exposing_inspect_environment(self):
        runner = fake_run_for({"docker image inspect": '["demo@sha256:' + "a"*64 + '"]'})
        values, error = docker_repo_digests("demo:latest", runner)
        self.assertEqual(error, None)
        self.assertEqual(len(values), 1)

    def test_runtime_with_absent_digest_marks_unknown(self):
        runner = fake_run_for({
            "docker ps -a": "test-app\n",
            "docker image inspect": "[]",
        })
        outcome = runtime_check(catalog_item(fixture(name="test-app", service="test-app",
                                                      container="test-app")),
                                runner=runner)
        self.assertEqual(outcome["installed"], "found")
        self.assertEqual(outcome["update_evidence"], "unknown_missing_repodigests")
        self.assertTrue(outcome["zimaos_service_name_resolves"])

    def test_runtime_does_not_claim_absent_container_is_not_installed(self):
        runner = fake_run_for({"docker ps -a": "different-container\n"})
        outcome = runtime_check(catalog_item(fixture(service="app", container="my-app")),
                                runner=runner)
        self.assertEqual(outcome["installed"], "not_found_by_expected_name")
        self.assertEqual(outcome["update_evidence"], "unknown_container_not_identified")
        self.assertTrue(outcome["zimaos_main_lookup_risk"])

    def test_api_base_rejects_remote_hosts_and_credentials(self):
        self.assertEqual(validate_api_base("http://127.0.0.1:4000"),
                         "http://127.0.0.1:4000")
        for value in ("http://example.com:4000",
                      "https://127.0.0.1:4000",
                      "http://user:pass@127.0.0.1:4000",
                      "http://127.0.0.1:4000/admin"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_api_base(value)

    def test_native_upgradable_absence_does_not_count_as_current(self):
        class MockResponse:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self, *_):
                return json.dumps({"data": [{"store_app_id": "other-app"}]}).encode()
        def opener(_url, timeout):
            return MockResponse()
        result = native_upgradable("http://127.0.0.1:4000", "io.github.mrpiracy94.demo",
                                   "demo", opener=opener)
        self.assertEqual(result, "not_listed_not_proof_of_current")

    def test_static_scan_from_temp_compose_tree(self):
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Apps" / "example" / "docker-compose.yml"
            path.parent.mkdir(parents=True)
            path.write_text(yaml.safe_dump(fixture(name="example", container="different").source))
            report = scan_catalog(Path(tmp))
            self.assertEqual(report["catalog_apps"], 1)
            self.assertEqual(report["counts"]["main_container_name_differs_from_service"], 1)


if __name__ == "__main__":
    unittest.main()
