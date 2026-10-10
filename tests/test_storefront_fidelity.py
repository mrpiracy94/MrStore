"""Testes de regressão da fidelidade visual e do catálogo da montra MrStore.

Não testam nem simulam instalações reais em ZimaOS.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web" / "index.html"
CSS = ROOT / "web" / "assets" / "site.css"
JS = ROOT / "web" / "assets" / "site.js"


class _Markup(HTMLParser):
    VOID = {"meta", "link", "img", "input", "source", "hr", "br", "wbr", "area"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id":
                self.ids.append(value)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"Elementos incorretos: fecho {tag}, atual {self.stack[-1:]}")
        else:
            self.stack.pop()


class FidelityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")
        cls.js = JS.read_text(encoding="utf-8")

    def test_real_html_structure_and_dom_refs(self):
        parser = _Markup()
        parser.feed(self.html)
        self.assertEqual(parser.errors, [])
        self.assertEqual(parser.stack, [])
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for key in re.findall(r'\$\("([^"]+)"\)', self.js):
            self.assertIn(key, parser.ids)

    def test_two_line_hero_and_svg_orbits(self):
        self.assertIn('class="hero-line-top"', self.html)
        self.assertIn('class="hero-line-accent"', self.html)
        self.assertEqual(len(re.findall(r'<svg\b', self.html)), 5)
        self.assertIn(".hero-lead h1 .hero-line-accent", self.css)

    def test_platform_cards_never_invent_integrations(self):
        cards = re.findall(r'<div class="system-card[^"]*"', self.html)
        self.assertEqual(len(cards), 11)
        self.assertIn("Catálogo v2 disponível", self.html)
        self.assertIn("Integração planeada", self.html)
        self.assertIn("As integrações", self.html)

    def test_actual_catalog_powers_cards_and_preview(self):
        self.assertIn('fetch("./index.json"', self.js)
        self.assertIn('fetch("./release-status.json"', self.js)
        self.assertIn("state.validated = verifyRelease", self.js)
        self.assertIn("renderShowcasePreview()", self.js)
        self.assertIn('id="showcase-apps"', self.html)
        self.assertIn('const BATCH_SIZE = 8;', self.js)
        self.assertIn('id="search"', self.html)
        self.assertIn('id="details"', self.html)
        self.assertNotIn("innerHTML", self.js)
        self.assertNotIn("500+ apps", self.html)

    def test_responsive_css_and_offline_assets(self):
        for fragment in ["@media(max-width:960px)", "@media(max-width:520px)",
                         "grid-template-columns:repeat(8,minmax(0,1fr))",
                         ".app-card-cover{display:none!important}", "[hidden]{display:none!important}"]:
            self.assertIn(fragment, self.css)
        for fragment in ['src="./assets/mark.svg"', 'src="./assets/mrstore-hero.webp"']:
            self.assertIn(fragment, self.html)
        self.assertIn("Content-Security-Policy", self.html)
        self.assertNotIn("https://cdn.", self.html)


if __name__ == "__main__":
    unittest.main()
