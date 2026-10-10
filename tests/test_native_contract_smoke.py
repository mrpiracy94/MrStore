"""Complete offline packaging smoke test for all platform adapters."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.native_contract_smoke import evaluate


class NativeContractSmokeTests(unittest.TestCase):
    def test_all_eleven_format_adapters_emit_single_approved_demo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            info = evaluate(root / "contracts", external=False)
            self.assertEqual(info["format_contracts_tested"], 11)
            self.assertEqual(info["real_installations_tested"], 0)
            self.assertFalse(info["native_certified"])
            evidence = json.loads(
                (root / "contracts/native-format-evidence.json").read_text())
            self.assertEqual(evidence["tested_platforms"][-1], "docker-linux")
            for key in ("docker_compose_config", "helm_lint", "helm_template"):
                self.assertFalse(evidence["external_parsers"][key])

    def test_cannot_overwrite_existing_format_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "contracts"
            evaluate(root)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                evaluate(root)


if __name__ == "__main__":
    unittest.main()
