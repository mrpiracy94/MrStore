"""Healthchecks smoke tests must prove both Docker architectures natively."""
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


class HealthchecksNativeRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load(
            (ROOT / ".github/workflows/verify-healthchecks-python-patches.yml")
            .read_text(encoding="utf-8")
        )

    def test_both_architectures_run_on_matching_native_runners(self):
        job = self.workflow["jobs"]["verify"]
        self.assertEqual(job["strategy"]["matrix"]["arch"], ["amd64", "arm64"])
        runner = job["runs-on"]
        self.assertIn("ubuntu-24.04-arm", runner)
        self.assertIn("ubuntu-24.04", runner)
        self.assertIn("matrix.arch == 'arm64'", runner)

    def test_no_arm64_qemu_fallback_or_security_bypass(self):
        job = self.workflow["jobs"]["verify"]
        steps = job["steps"]
        uses = [str(step.get("uses", "")) for step in steps]
        self.assertFalse(any("setup-qemu-action" in action for action in uses))
        names = {str(step.get("name", "")) for step in steps}
        self.assertIn("Prove native runner matches scanned CPU architecture", names)
        self.assertIn("Scan exact patched image", names)
        self.assertIn("Block on any remaining HIGH CRITICAL or incomplete Trivy scan", names)
        self.assertIn("Verify login UI, default web port, persistent config on this architecture", names)
        self.assertFalse(any(step.get("continue-on-error") for step in steps))


if __name__ == "__main__":
    unittest.main()
