"""No-Docker/network unit tests for the read-only OCI update detector."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from oci_installed_update_check import (canonical_repository, check, inspect_local,
                                        remote_config_digest, main)

A = "sha256:" + "a" * 64
B = "sha256:" + "b" * 64


class FakeCommands:
    def __init__(self, *, local=A, image="lscr.io/linuxserver/sonarr:latest",
                 platform="linux/amd64", remote=A, remote_error=False):
        self.calls = []
        self.local = local
        self.image = image
        self.platform = platform
        self.remote = remote
        self.remote_error = remote_error

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if args[:3] == ["docker", "container", "inspect"]:
            if args[-1] == "{{.Image}}":
                value = self.local
            elif args[-1] == "{{.Config.Image}}":
                value = self.image
            else:
                return subprocess.CompletedProcess(args, 1, "", "not found")
        elif args[:3] == ["docker", "image", "inspect"]:
            value = self.platform
        elif args[:2] == ["crane", "manifest"]:
            if self.remote_error:
                return subprocess.CompletedProcess(args, 1, "", "401 Authorization: secret")
            value = json.dumps({
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": self.remote},
            })
        else:
            raise AssertionError(f"Unexpected or modifying command: {args}")
        return subprocess.CompletedProcess(args, 0, value + "\n", "")


class OciImageUpdateTests(unittest.TestCase):
    def test_detects_real_remote_change_without_any_repodigests(self):
        fake = FakeCommands(remote=B)
        r = check("sonarr", runner=fake)
        self.assertEqual(r["status"], "candidate_update")
        self.assertEqual(r["remote_config_digest"], B)
        self.assertFalse(r["zimaos_native_badge_verified"])
        self.assertFalse(r["updated_or_pulled"])
        self.assertEqual(fake.calls[-1][:2], ["crane", "manifest"])
        self.assertFalse(any("pull" in x or "run" in x or "up" in x
                             for command in fake.calls for x in command))

    def test_same_image_means_no_new_remote_build_for_platform(self):
        r = check("sonarr", runner=FakeCommands(remote=A))
        self.assertEqual(r["status"], "same_image")

    def test_checks_target_architecture_from_local_docker(self):
        fake = FakeCommands(platform="linux/arm64/v8", remote=B)
        self.assertEqual(check("sonarr", runner=fake)["status"], "candidate_update")
        self.assertEqual(fake.calls[-1],
                         ["crane", "manifest", "--platform", "linux/arm64/v8",
                          "lscr.io/linuxserver/sonarr:latest"])

    def test_compares_actual_container_id_not_retagged_local_image(self):
        fake = FakeCommands(local=A, remote=B)
        r = check("sonarr", runner=fake)
        self.assertEqual(r["local_image_id"], A)
        self.assertEqual(r["status"], "candidate_update")

    def test_manual_explicit_target_pinned_image_allowed(self):
        fake = FakeCommands(image="lscr.io/linuxserver/sonarr:latest@" + A, remote=B)
        r = check("sonarr", target="lscr.io/linuxserver/sonarr:latest@" + B, runner=fake)
        self.assertEqual(r["status"], "candidate_update")

    def test_immutable_only_default_does_not_claim_up_to_date(self):
        fake = FakeCommands(image="lscr.io/linuxserver/sonarr:latest@" + A)
        r = check("sonarr", runner=fake)
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["reason"], "immutable_reference_no_floating_target")
        self.assertFalse(any(c[0] == "crane" for c in fake.calls))

    def test_different_repositories_refused_to_prevent_false_update(self):
        fake = FakeCommands()
        r = check("sonarr", target="ghcr.io/other/vendor:latest", runner=fake)
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["reason"], "installed_and_target_repositories_differ")

    def test_registry_error_preserves_unknown_not_fake_current(self):
        fake = FakeCommands(remote_error=True)
        r = check("sonarr", runner=fake)
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["reason"], "command_failed")
        self.assertNotIn("secret", json.dumps(r))

    def test_rejects_digest_without_manifest_config(self):
        class Runner(FakeCommands):
            def __call__(self, args, **kwargs):
                if args[:2] == ["crane", "manifest"]:
                    self.calls.append(args)
                    return subprocess.CompletedProcess(
                        args, 0, '{"schemaVersion":2,"manifests":[]}', "")
                return super().__call__(args, **kwargs)
        r = check("sonarr", runner=Runner())
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["reason"], "unsupported_registry_manifest_type")

    def test_rejects_unknown_platform(self):
        r = check("sonarr", runner=FakeCommands(platform="linux/ppc64le"))
        self.assertEqual(r["reason"], "unsupported_or_ambiguous_platform")
        self.assertEqual(r["status"], "unknown")

    def test_rejects_bad_local_image_id(self):
        r = check("sonarr", runner=FakeCommands(local="not-a-config-digest"))
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(r["reason"], "invalid_installed_image_id")

    def test_repo_normalization(self):
        self.assertEqual(canonical_repository("ubuntu:latest"),
                         "docker.io/library/ubuntu")
        self.assertEqual(canonical_repository("docker.io/library/ubuntu:latest"),
                         "docker.io/library/ubuntu")
        self.assertEqual(canonical_repository("linuxserver/sonarr:latest"),
                         "docker.io/linuxserver/sonarr")
        self.assertEqual(canonical_repository("lscr.io/linuxserver/sonarr:latest@" + A),
                         "lscr.io/linuxserver/sonarr")

    def test_invalid_container_rejected_before_any_commands(self):
        fake = FakeCommands()
        r = check("--evil", runner=fake)
        self.assertEqual(r["status"], "unknown")
        self.assertFalse(fake.calls)

    def test_cli_output_requires_no_docker_if_mocked(self):
        import unittest.mock
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch(
                "oci_installed_update_check.check",
                return_value={"status": "candidate_update", "reason": "test"}):
            result = Path(tmp, "out.json")
            self.assertEqual(main(["--container", "sonarr", "--output", str(result)]), 0)
            self.assertEqual(json.loads(result.read_text())["status"], "candidate_update")


if __name__ == "__main__":
    unittest.main()
