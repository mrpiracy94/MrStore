"""Unresolved Compose secrets must never be published as one-click ZimaOS apps.

The official v2 builder strips services.*.x-casaos, including env prompts.
This is a static release quarantine policy, not an installed-device test.
"""
from types import SimpleNamespace
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from release_catalog import insecure_defaults, REQUIRED_COMPOSE_VARIABLE


def fixture(env):
    return SimpleNamespace(source={"services": {"example": {
        "image": "example/image:1.2.3",
        "environment": env,
    }}})


class RequiredInstallerEnvironmentTests(unittest.TestCase):
    def test_missing_required_secret_is_quarantined(self):
        for text in (
            "PASSWORD=${EXAMPLE_PASSWORD:?Configure password before deploy}",
            "PASSWORD=${EXAMPLE_PASSWORD?Configure password before deploy}",
            "API_KEY=${EXAMPLE_KEY:?}",
        ):
            with self.subTest(value=text):
                errors = insecure_defaults(fixture([text]))
                self.assertTrue(any("required Compose installation variables"
                                    in e for e in errors), errors)
                self.assertFalse(any("CHANGE_ME" in e for e in errors))

    def test_required_in_yaml_dictionary_is_quarantined(self):
        errors = insecure_defaults(fixture({
            "PASSWORD": "${EXAMPLE_PASSWORD:?required}",
            "TZ": "Europe/Lisbon",
        }))
        self.assertTrue(any("required Compose installation variables" in e
                            for e in errors))

    def test_optional_interpolation_is_not_quarantined_by_this_rule(self):
        for text in (
            "URL=${PUBLIC_URL:-http://zimaos.local}",
            "PORT=${PUBLIC_PORT-3000}",
            "TZ=Europe/Lisbon",
        ):
            with self.subTest(value=text):
                self.assertFalse(any("required Compose installation variables" in e
                                     for e in insecure_defaults(fixture([text]))))

    def test_required_interpolation_in_non_environment_compose_values(self):
        # Compose resolves these before a ZimaOS installer can ask for secrets.
        for field, value in (
            ("command", ["--token=${REQUIRED_TOKEN:?set token}"]),
            ("labels", {"api.token": "${REQUIRED_TOKEN?set token}"}),
            ("hostname", "${REQUIRED_HOSTNAME:?set hostname}"),
        ):
            with self.subTest(field=field):
                app = fixture(["TZ=Europe/Lisbon"])
                app.source["services"]["example"][field] = value
                self.assertTrue(any("required Compose installation variables" in e
                                    for e in insecure_defaults(app)))

    def test_zimaos_documentation_is_not_runtime_secret_interpolation(self):
        app = fixture(["TZ=Europe/Lisbon"])
        app.source["services"]["example"]["x-casaos"] = {
            "description": "${EXAMPLE:?documentation only}"
        }
        self.assertFalse(any("required Compose installation variables" in e
                             for e in insecure_defaults(app)))

    def test_public_change_me_also_stays_quarantined(self):
        self.assertTrue(any("default credentials not configured" in x
                            for x in insecure_defaults(fixture(["PASSWORD=CHANGE_ME"]))))

    def test_required_top_level_volume_variables_cannot_escape_gate(self):
        app = fixture(["TZ=Europe/Lisbon"])
        app.source["volumes"] = {"shared": {
            "driver_opts": {"device": "${DATA_ROOT:?configure data root}"}}}
        reasons = insecure_defaults(app)
        self.assertTrue(any("compose: required Compose installation variables" in x
                            for x in reasons), reasons)

    def test_descriptive_root_metadata_does_not_require_secret(self):
        app = fixture(["TZ=Europe/Lisbon"])
        app.source["x-casaos"] = {"description": "${FAKE_SECRET:?just documentation}"}
        self.assertFalse(any("required Compose installation variables" in x
                             for x in insecure_defaults(app)))

    def test_change_me_in_runtime_command_or_labels_is_quarantined(self):
        for field, value in (
            ("command", ["--admin-password=CHANGE_ME"]),
            ("labels", {"admin.password": "CHANGE_ME"}),
        ):
            with self.subTest(field=field):
                app = fixture(["TZ=Europe/Lisbon"])
                app.source["services"]["example"][field] = value
                self.assertTrue(any("default credentials not configured" in e
                                    for e in insecure_defaults(app)))

    def test_pattern_does_not_match_plain_container_variables(self):
        self.assertIsNone(REQUIRED_COMPOSE_VARIABLE.search(
            "PASSWORD=valid_private_value_without_interpolation"))


if __name__ == "__main__":
    unittest.main()
