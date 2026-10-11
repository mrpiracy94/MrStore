"""Prevent re-introduction of moving GitHub Action tags."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_action_pins import inspect_repo, inspect_workflow

SHA = "a" * 40


class ActionPinTests(unittest.TestCase):
    def test_tag_is_rejected(self):
        self.assertTrue(inspect_workflow("steps:\n  - uses: actions/checkout@v7\n", "example.yml"))

    def test_full_sha_and_local_actions_accepted(self):
        self.assertFalse(inspect_workflow(
            "steps:\n  - uses: actions/checkout@" + SHA +
            "\n  - uses: ./.github/actions/security\n", "safe.yml"))

    def test_short_sha_rejected(self):
        self.assertTrue(inspect_workflow("  uses: docker/login-action@deadbeef\n", "x"))

    def test_remote_reusable_workflow_requires_sha(self):
        self.assertTrue(inspect_workflow("uses: example/repo/.github/workflows/a.yml@main\n", "x"))
        self.assertFalse(inspect_workflow("uses: example/repo/.github/workflows/a.yml@" + SHA + "\n", "x"))

    def test_repo_scan_detects_all_workflow_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / ".github/workflows"
            folder.mkdir(parents=True)
            (folder / "a.yml").write_text("steps:\n  - uses: actions/checkout@" + SHA + "\n")
            (folder / "b.yaml").write_text("steps:\n  - uses: actions/checkout@v7\n")
            n, risks = inspect_repo(root)
            self.assertEqual(n, 2)
            self.assertEqual(len(risks), 1)

    def test_real_repository_all_actions_pinned(self):
        n, risks = inspect_repo(ROOT)
        self.assertGreaterEqual(n, 40)
        self.assertFalse(risks, "\\n".join(risks))


if __name__ == "__main__":
    unittest.main()
