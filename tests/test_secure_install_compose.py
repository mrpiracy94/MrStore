"""Safe per-install Compose generation; no credentials in Git."""
import copy
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from secure_install_compose import NeedsConfiguration, prepare_from_repo, resolve_manifest


class SecureInstallTests(unittest.TestCase):
    def test_immich_two_services_share_database_password(self):
        doc = {"services": {
            "immich-server": {"environment": ["DB_PASSWORD=CHANGE_ME"]},
            "postgres": {"environment": ["POSTGRES_PASSWORD=CHANGE_ME"]},
        }}
        result, changed = resolve_manifest(doc, "immich", password_factory=lambda: "strong-one")
        self.assertEqual(result["services"]["immich-server"]["environment"],
                         ["DB_PASSWORD=strong-one"])
        self.assertEqual(result["services"]["postgres"]["environment"],
                         ["POSTGRES_PASSWORD=strong-one"])
        self.assertEqual(len(changed), 2)
        self.assertEqual(doc["services"]["postgres"]["environment"], ["POSTGRES_PASSWORD=CHANGE_ME"])

    def test_karakeep_meili_secret_shared_and_auth_unique(self):
        counter = iter(["unique-one", "unique-two"])
        doc = {"services": {
            "app": {"environment": ["NEXTAUTH_SECRET=CHANGE_ME", "MEILI_MASTER_KEY=CHANGE_ME"]},
            "meili": {"environment": ["MEILI_MASTER_KEY=CHANGE_ME"]},
        }}
        result, _ = resolve_manifest(doc, "karakeep", password_factory=lambda: next(counter))
        app = result["services"]["app"]["environment"]
        meili = result["services"]["meili"]["environment"]
        self.assertNotEqual(app[0].split("=", 1)[1], app[1].split("=", 1)[1])
        self.assertEqual(app[1], meili[0])

    def test_cloudflare_token_not_invented(self):
        doc = {"services": {"cloudflared": {
            "environment": ["TUNNEL_TOKEN=CHANGE_ME"]}}}
        with self.assertRaises(NeedsConfiguration):
            resolve_manifest(doc, "cloudflared")
        out, _ = resolve_manifest(doc, "cloudflared", {"TUNNEL_TOKEN": "external-issued-token"})
        self.assertEqual(out["services"]["cloudflared"]["environment"][0],
                         "TUNNEL_TOKEN=external-issued-token")

    def test_external_database_cannot_be_invented(self):
        doc = {"services": {"bookstack": {
            "environment": ["DB_HOST=CHANGE_ME_DB_HOST", "DB_PASSWORD=CHANGE_ME",
                            "APP_KEY=CHANGE_ME"]}}}
        with self.assertRaises(NeedsConfiguration):
            resolve_manifest(doc, "bookstack")
        out, _ = resolve_manifest(doc, "bookstack",
                                  {"DB_HOST": "mariadb.internal", "DB_PASSWORD": "external-actual-pass"})
        values = out["services"]["bookstack"]["environment"]
        self.assertTrue(any(x.startswith("APP_KEY=base64:") for x in values))

    def test_generates_distinct_secrets(self):
        doc = {"services": {"lldap": {"environment": {
            "LLDAP_JWT_SECRET": "CHANGE_ME", "LLDAP_KEY_SEED": "CHANGE_ME",
            "LLDAP_LDAP_USER_PASS": "CHANGE_ME"}}}}
        counter = iter(["firststrong", "secondstrong", "thirdstrong"])
        out, _ = resolve_manifest(doc, "lldap", password_factory=lambda: next(counter))
        self.assertEqual(len(set(out["services"]["lldap"]["environment"].values())), 3)

    def test_refuses_any_unhandled_secret_or_plain_placeholder(self):
        doc = {"services": {"svc": {"image": "example:1", "environment": ["UNSAFE=CHANGE_ME"]}}}
        with self.assertRaises(NeedsConfiguration):
            resolve_manifest(doc, "some-app")
        doc = {"services": {"svc": {"command": ["CHANGE_ME"]}}}
        with self.assertRaises(NeedsConfiguration):
            resolve_manifest(doc, "some-app")

    def test_private_file_no_overwrite_and_no_write_to_repo(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace) / "source"
            path = root / "Apps" / "mariadb" / "docker-compose.yml"
            path.parent.mkdir(parents=True)
            path.write_text("name: mariadb\nservices:\n  maria:\n    image: mariadb:11\n    environment:\n      - MYSQL_ROOT_PASSWORD=CHANGE_ME\n")
            out = Path(workspace) / "private.yml"
            with patch("secure_install_compose.secrets.token_urlsafe", return_value="secret-in-test"):
                keys = prepare_from_repo("mariadb", out, root=root)
            self.assertEqual(keys, ["MYSQL_ROOT_PASSWORD"])
            self.assertIn("secret-in-test", out.read_text())
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                prepare_from_repo("mariadb", out, root=root)
            with self.assertRaises(NeedsConfiguration):
                prepare_from_repo("mariadb", root / "inside.yml", root=root)


if __name__ == "__main__":
    unittest.main()
