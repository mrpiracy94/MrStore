"""Offline regression checks for the online storefront asset scanner."""
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from scripts.asset_audit_online import (
    OWN_RAW_PREFIX, audit, check_url, ensure_public_https, is_image,
)


class ArtworkAuditTests(unittest.TestCase):
    def test_image_signatures(self):
        self.assertTrue(is_image(b"\x89PNG\r\n\x1a\nmore", "image/png"))
        self.assertTrue(is_image(b"\xff\xd8\xffmore", "image/jpeg"))
        self.assertTrue(is_image(b"RIFF1234WEBPmore", "image/webp"))
        self.assertTrue(is_image(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                                 "image/svg+xml"))
        self.assertFalse(is_image(b"<html>Not an image</html>", "image/png"))
        self.assertFalse(is_image(b"RIFF1234WAVEmore", "image/webp"))

    def test_https_and_public_dns_only(self):
        with self.assertRaises(ValueError):
            ensure_public_https("http://example.org/icon.png")
        with patch("scripts.asset_audit_online.socket.getaddrinfo",
                   return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                                  ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                ensure_public_https("https://example.org/icon.png")
        with patch("scripts.asset_audit_online.socket.getaddrinfo",
                   return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                                  ("8.8.8.8", 443))]):
            ensure_public_https("https://example.org/icon.png")

    def test_http_404_is_broken_and_timeout_is_inconclusive(self):
        from urllib.error import HTTPError
        with patch("scripts.asset_audit_online.ensure_public_https"), patch(
                "scripts.asset_audit_online.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = HTTPError(
                "https://example.org/icon.png", 404, "Not Found", {}, None)
            self.assertEqual("broken", check_url("https://example.org/icon.png")["status"])
            opener.return_value.open.side_effect = TimeoutError("timeout")
            self.assertEqual("inconclusive",
                             check_url("https://example.org/icon.png")["status"])

    def test_dedupe_and_do_not_misstate_premerge_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Apps/test").mkdir(parents=True)
            (root / "branding").mkdir()
            (root / "branding/mrstore-icon.svg").write_text("<svg></svg>")
            (root / "store-config.json").write_text(
                '{"icon": "' + OWN_RAW_PREFIX + 'branding/mrstore-icon.svg"}')
            (root / "Apps/test/docker-compose.yml").write_text(
                "x-casaos:\n"
                "  icon: https://assets.example.org/app.png\n"
                "  thumbnail: https://assets.example.org/app.png\n")
            with patch("scripts.asset_audit_online.check_url",
                       return_value={"status": "ok"}) as checker:
                result = audit(root, defer_unpublished=True)
            self.assertEqual(3, result["references"])
            self.assertEqual(2, result["unique_urls"])
            self.assertEqual({"ok": 1, "deferred": 1}, result["counts"])
            self.assertFalse(result["complete"])
            checker.assert_called_once()


if __name__ == "__main__":
    unittest.main()
