"""Smoke-check local secret generation against every real app with CHANGE_ME."""
import json
from pathlib import Path
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from secure_install_compose import EXTERNAL_KEYS, PLACEHOLDER, resolve_manifest


class ActualSecretManifests(unittest.TestCase):
    def test_all_real_placeholder_apps_are_resolvable_without_shared_defaults(self):
        count = 0
        for path in sorted((ROOT / "Apps").glob("*/docker-compose.yml")):
            source = yaml.safe_load(path.read_text(encoding="utf-8"))
            services = source.get("services") or {}
            placeholders = {}
            for spec in services.values():
                env = spec.get("environment") or []
                pairs = env.items() if isinstance(env, dict) else (
                    x.split("=", 1) for x in env if isinstance(x, str) and "=" in x)
                for k, v in pairs:
                    if isinstance(v, str) and PLACEHOLDER.fullmatch(v):
                        placeholders[k] = v
            if not placeholders:
                continue
            count += 1
            app = path.parent.name
            external = {key: f"configured-external-{key.lower()}"
                        for key in EXTERNAL_KEYS.get(app, set()) if key in placeholders}
            with self.subTest(app=app):
                ready, changed = resolve_manifest(source, app, provided=external)
                self.assertEqual(set(changed), set(placeholders))
                for name, spec in ready["services"].items():
                    env = spec.get("environment") or []
                    pairs = env.items() if isinstance(env, dict) else (
                        x.split("=", 1) for x in env if isinstance(x, str) and "=" in x)
                    for key, val in pairs:
                        self.assertFalse(isinstance(val, str) and PLACEHOLDER.fullmatch(val),
                                         f"{app}/{name}: {key} left unconfigured")
                self.assertEqual(set(services), set(ready["services"]))
        self.assertGreaterEqual(count, 10)


if __name__ == "__main__":
    unittest.main()
