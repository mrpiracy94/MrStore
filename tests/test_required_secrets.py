"""Tests for the Docker Compose required-secret gate; no Docker daemon needed."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_required_secrets import check_one, required_by_app, verify


class RequiredSecretsTests(unittest.TestCase):
    def test_all_expected_apps_are_scoped(self):
        required = required_by_app()
        self.assertEqual(len(required), 19)
        self.assertEqual(sum(len(names) for names in required.values()), 26)
        self.assertEqual(required["immich"], ["IMMICH_DB_PASSWORD"])
        self.assertEqual(required["karakeep"],
                         ["KARAKEEP_MEILI_MASTER_KEY", "KARAKEEP_NEXTAUTH_SECRET"])

    def test_each_missing_or_empty_secret_blocks_compose(self):
        invoked = []

        def fake_run(command, **kwargs):
            invoked.append((command, kwargs))
            required = ["A_SECRET", "B_SECRET"]
            missing = next((key for key in required if not kwargs["env"].get(key)), None)
            error = f"required variable {missing} is missing or empty" if missing else ""
            return subprocess.CompletedProcess(command, 1 if missing else 0, "", error)

        result = check_one(Path("/tmp/dummy/docker-compose.yml"),
                           ["A_SECRET", "B_SECRET"], fake_run)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checks"], 5)
        self.assertTrue(all(x[0][-2:] == ["config", "--quiet"] for x in invoked))
        self.assertFalse(any({"up", "pull", "build", "run", "start", "exec"} &
                             set(x[0]) for x in invoked))
        self.assertFalse(any("CHANGE_ME" in str(x[1]) for x in invoked))

    def test_unrelated_parser_error_cannot_appear_as_a_valid_secret_gate(self):
        def invalid_run(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "", "invalid YAML")
        result = check_one(Path("/tmp/dummy/docker-compose.yml"), ["A_SECRET"],
                           invalid_run)
        self.assertFalse(result["ok"])
        self.assertTrue(any("synthetic values" in x for x in result["failures"]))
        self.assertTrue(any("missing did not fail" in x for x in result["failures"]))

    def test_reports_are_never_marked_zimaos_runtime_verified(self):
        def success_with_required_error(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "", "")
        outcome = check_one(Path("/tmp/dummy/docker-compose.yml"), ["A_SECRET"],
                            success_with_required_error)
        self.assertFalse(outcome["ok"])


if __name__ == "__main__":
    unittest.main()
