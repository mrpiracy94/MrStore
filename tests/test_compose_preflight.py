"""Ensure Compose preflight cannot start, build, or pull app images."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from compose_preflight import check_manifest, scan, to_markdown


class ComposePreflightTests(unittest.TestCase):
    def test_check_only_invokes_docker_compose_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "Apps" / "demo" / "docker-compose.yml"
            path.parent.mkdir(parents=True)
            path.write_text("services:\n  demo:\n    image: example/demo:1\n")
            runner = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
            self.assertTrue(check_manifest(path, root, runner=runner)["ok"])
            args, opts = runner.call_args
            command = args[0]
            self.assertEqual(command[:2], ["docker", "compose"])
            self.assertEqual(command[-3:], ["config", "--quiet", "--no-interpolate"])
            self.assertFalse(set(command) & {"up", "run", "build", "pull", "exec", "start"})
            self.assertTrue(opts["capture_output"])
            self.assertLessEqual(opts["timeout"], 35)

    def test_compose_parser_failure_and_timeout_never_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "Apps" / "invalid" / "docker-compose.yml"
            runner = Mock(return_value=subprocess.CompletedProcess([], 1, "", "invalid YAML"))
            failure = check_manifest(path, root, runner=runner)
            self.assertFalse(failure["ok"])
            self.assertIn("invalid YAML", failure["reason"])
            runner = Mock(side_effect=subprocess.TimeoutExpired("docker compose", 1))
            self.assertFalse(check_manifest(path, root, runner=runner)["ok"])

    def test_scan_fails_closed_and_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for app in ("one", "two"):
                manifest = root / "Apps" / app / "docker-compose.yml"
                manifest.parent.mkdir(parents=True)
                manifest.write_text("services: {}\n")
            def runner(command, **kwargs):
                rc = 1 if "/two/" in command[command.index("-f") + 1] else 0
                return subprocess.CompletedProcess(command, rc, "", "invalid dependency" if rc else "")
            result = scan(root, workers=2, runner=runner)
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["passed"], 1)
            self.assertEqual(result["failed"], 1)
            self.assertFalse(result["runtime_verified"])
            self.assertEqual([x["app"] for x in result["results"]], ["one", "two"])
            self.assertIn("invalid dependency", to_markdown(result))

    def test_scan_without_apps_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "No app"):
                scan(Path(tmp))


if __name__ == "__main__":
    unittest.main()
