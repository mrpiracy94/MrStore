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
    catalog_item, compare_digests, docker_compose_names, docker_repo_digests, is_latest,
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
        # Generic docker-ps fixture output is NOT proof of project/service
        # labels. Return an empty filtered listing unless specified.
        if "--filter" in command and not any(k.startswith("label=") for k in values):
            return subprocess.CompletedProcess(command, 0, "", "")
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
            "--format {{.Image}}": "sha256:" + "c" * 64,
            "docker container inspect": "example/installed:latest",
            "docker image inspect": "[]",
        })
        outcome = runtime_check(catalog_item(fixture(name="test-app", service="test-app",
                                                      container="test-app")),
                                runner=runner)
        self.assertEqual(outcome["installed"], "found")
        self.assertEqual(outcome["update_evidence"], "unknown_missing_repodigests")
        self.assertTrue(outcome["zimaos_service_name_resolves"])

    def test_runtime_inspects_immutable_running_image_id_not_mutable_tag(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            if command[:3] == ["docker", "ps", "-a"]:
                value = "test-app\n"
            elif command[:3] == ["docker", "container", "inspect"]:
                value = ("sha256:" + "c" * 64) if "{{.Image}}" in command else "example/installed:old"
            elif command[:3] == ["docker", "image", "inspect"]:
                value = '["example/installed@sha256:' + "a" * 64 + '"]'
            else:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, value, "")
        item = catalog_item(fixture(name="test-app", service="test-app",
                                    container="test-app", image="example/catalog:latest"))
        result = runtime_check(item, runner=runner)
        self.assertEqual(result["installed_image"], "example/installed:old")
        self.assertEqual(result["installed_image_id"], "sha256:" + "c" * 64)
        self.assertTrue(any(c[:3] == ["docker", "image", "inspect"]
                            and c[3] == "sha256:" + "c" * 64 for c in calls))
        self.assertFalse(any(c[:3] == ["docker", "image", "inspect"]
                             and c[3] == "example/installed:old" for c in calls))
        self.assertEqual(result["update_evidence"], "unknown_remote_not_checked")

    def test_a_re_pulled_latest_tag_does_not_hide_running_old_image(self):
        """A moved latest tag must never be mistaken for the running image."""
        old = "sha256:" + "a" * 64
        new = "sha256:" + "b" * 64
        running_id = "sha256:" + "c" * 64
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            if command[:3] == ["docker", "ps", "-a"]:
                value = "test-app"
            elif command[:3] == ["docker", "container", "inspect"]:
                value = running_id if "{{.Image}}" in command else "example/installed:latest"
            elif command[:3] == ["docker", "image", "inspect"]:
                # If accidentally inspected by tag, Docker would return the
                # newly pulled digest, producing a false "up to date".
                value = json.dumps(["example/installed@" + old] if command[3] == running_id
                                   else ["example/installed@" + new])
            elif command[:2] == ["crane", "digest"]:
                value = new
            else:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, value, "")

        item = catalog_item(fixture(name="test-app", service="test-app",
                                    container="test-app", image="example/installed:latest"))
        result = runtime_check(item, check_registry=True, runner=runner)
        self.assertEqual(result["update_evidence"], "digest_differs_review_required")
        self.assertTrue(any(c[:3] == ["docker", "image", "inspect"] and c[3] == running_id
                            for c in calls))
        self.assertFalse(any(c[:3] == ["docker", "image", "inspect"] and
                             c[3] == "example/installed:latest" for c in calls))

    def test_invalid_image_id_cannot_fall_back_to_mutable_tag(self):
        def runner(command, **kwargs):
            if command[:3] == ["docker", "ps", "-a"]:
                value = "test-app"
            elif command[:3] == ["docker", "container", "inspect"]:
                value = "malformed-id" if "{{.Image}}" in command else "demo:latest"
            elif command[:3] == ["docker", "image", "inspect"]:
                self.fail("Do not inspect a mutable tag when image ID is invalid")
            else:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, value, "")

        item = catalog_item(fixture(name="test-app", service="test-app",
                                    container="test-app"))
        result = runtime_check(item, runner=runner)
        self.assertEqual(result["update_evidence"], "unknown_local_inspection_failed")
        self.assertEqual(result["docker_image_error"], "invalid_installed_image_id")

    def test_scoped_compose_labels_identify_container_without_name_guessing(self):
        calls = []
        image_id = "sha256:" + "c" * 64

        def runner(command, **kwargs):
            calls.append(command)
            if command[:3] == ["docker", "ps", "-a"]:
                value = "my-real-container" if "--filter" in command else "my-real-container\\nother-app"
            elif command[:3] == ["docker", "container", "inspect"]:
                value = image_id if "{{.Image}}" in command else "example/app:latest"
            elif command[:3] == ["docker", "image", "inspect"]:
                value = "[]"
            else:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, value, "")

        item = catalog_item(fixture(name="test-app", service="app",
                                    container="name-that-is-not-running"))
        outcome = runtime_check(item, runner=runner)
        self.assertEqual(outcome["installed"], "found")
        self.assertEqual(outcome["container_resolution"], "compose_project_and_service_labels")
        self.assertFalse(outcome["zimaos_service_name_resolves"])
        self.assertEqual(outcome["installed_image_id"], image_id)
        filters = next(c for c in calls if c[:3] == ["docker", "ps", "-a"] and "--filter" in c)
        self.assertIn("label=com.docker.compose.project=test-app", filters)
        self.assertIn("label=com.docker.compose.service=app", filters)
        self.assertTrue(any(c[:3] == ["docker", "container", "inspect"] and
                            c[3] == "my-real-container" for c in calls))

    def test_multiple_matching_compose_replicas_does_not_guess(self):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            if command[:3] == ["docker", "ps", "-a"]:
                value = "project-app-1\\nproject-app-2"
                return subprocess.CompletedProcess(command, 0, value, "")
            self.fail("Ambiguous Compose containers must not be inspected")

        item = catalog_item(fixture(name="project", service="app", container=None))
        outcome = runtime_check(item, runner=runner)
        self.assertEqual(outcome["installed"], "ambiguous_multiple_main_containers")
        self.assertEqual(outcome["update_evidence"], "unknown_ambiguous_main_containers")

    def test_label_lookup_fails_closed_on_missing_project(self):
        names, err = docker_compose_names("", "app")
        self.assertIsNone(names)
        self.assertEqual(err, "invalid_compose_identity")

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
