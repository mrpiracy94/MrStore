"""Prevent bypassing warnings for unsafe default credentials in the public storefront."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorefrontSecurityWarnings(unittest.TestCase):
    def test_published_inventory_is_required_for_direct_downloads(self):
        site = (ROOT / "web/assets/site.js").read_text()
        self.assertIn('fetch("./security-inventory.json"', site)
        self.assertIn('inventory.apps_total !== state.apps.length', site)
        self.assertIn('credential_placeholder', site)
        self.assertIn('weak_example_secret', site)
        self.assertIn('compose.hidden = !url || !Array.isArray(codes) || blocked;', site)
        self.assertIn('state.security = null;', site)

    def test_warning_is_visible_in_app_details(self):
        html = (ROOT / "web/index.html").read_text()
        self.assertIn('id="details-security" role="status"', html)
        self.assertIn('id="details-compose"', html)

    def test_node_syntax_is_checked_in_github_actions(self):
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        self.assertIn("node --check web/assets/site.js", workflow)


if __name__ == "__main__":
    unittest.main()
