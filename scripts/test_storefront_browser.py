"""Smoke tests for the MrStore storefront in real Chromium.
--fixture: use clearly labelled isolated sample data in pull requests.
Without --fixture: require the published approved dist/index.json.
"""
import argparse
import json
import pathlib
import shutil
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--fixture", action="store_true", help="Use only test fixtures, never production data")
args = parser.parse_args()

tmp = tempfile.TemporaryDirectory() if args.fixture else None
dist = pathlib.Path(tmp.name) if tmp else ROOT / "dist"
if args.fixture:
    (dist / "web").mkdir(parents=True)
    (dist / "assets" / "branding").mkdir(parents=True)
    shutil.copy2(ROOT / "web" / "index.html", dist / "index.html")
    for filename in ("style.css", "app.js", "hero.svg"):
        shutil.copy2(ROOT / "web" / filename, dist / "web" / filename)
    for filename in ("mrstore-icon.svg", "mrstore-banner.svg"):
        shutil.copy2(ROOT / "assets" / "branding" / filename, dist / "assets" / "branding" / filename)
    sample = [
        {"id": "plex", "name": "Plex", "category": "Media", "tagline": "Filmes e séries"},
        {"id": "immich", "name": "Immich", "category": "Graphics", "tagline": "Fotografias privadas"},
        {"id": "nextcloud", "name": "Nextcloud", "category": "Cloud", "tagline": "Os teus ficheiros"},
        {"id": "jellyfin", "name": "Jellyfin", "category": "Media", "tagline": "Biblioteca multimédia"},
    ]
    (dist / "index.json").write_text(json.dumps({"version": 2, "apps": sample}), encoding="utf-8")

assert (dist / "index.json").exists(), "Missing approved dist/index.json"
assert (dist / "index.html").exists(), "Missing dist/index.html"

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(dist), **kwargs)
server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_port}/"

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in [(1536, 864), (390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(base, wait_until="networkidle")
            assert page.locator(".showcase").is_visible()
            assert page.locator(".category-tile").count() == 8
            assert page.locator("#status").is_visible()
            assert "Não foi possível carregar" not in page.locator("#status").inner_text()
            assert page.locator(".card").count() == len(sample) if args.fixture else page.locator(".card").count() > 0
            assert not errors, errors
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"), f"Horizontal overflow at {width}px"
            prefix = "fixture-" if args.fixture else "approved-"
            page.screenshot(path=str(ROOT / f"storefront-{prefix}{width}.png"), full_page=True)
            if width == 1536:
                page.locator("#search").fill("zzzz-no-match")
                assert page.locator(".card").count() == 0
                page.locator("#show-all").click()
                assert page.locator("#search").input_value() == ""
                page.locator("#sort").select_option("reverse")
                assert page.locator("#sort").input_value() == "reverse"
                page.locator(".category-tile").filter(has_text="Multimédia").click()
                assert page.locator(".card").count() > 0
            page.close()
        browser.close()
finally:
    server.shutdown()
    if tmp:
        tmp.cleanup()
