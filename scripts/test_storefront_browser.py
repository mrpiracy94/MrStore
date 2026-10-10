import json
import pathlib
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)

# Use the approved publication output. Never invent apps in a production build.
assert (DIST / "index.json").exists(), "Build the approved catalog before browser tests"
assert (DIST / "index.html").exists(), "Copy the storefront into dist before browser tests"

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(DIST), **kwargs)
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
            assert not errors, errors
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            assert not overflow, f"Horizontal overflow at {width}px"
            page.screenshot(path=str(ROOT / f"storefront-{width}.png"), full_page=True)
            if width == 1536:
                page.locator("#search").fill("zzzz-no-match")
                assert page.locator(".card").count() == 0
                page.locator("#show-all").click()
                assert page.locator("#search").input_value() == ""
                page.locator("#sort").select_option("reverse")
                assert page.locator("#sort").input_value() == "reverse"
            page.close()
        browser.close()
finally:
    server.shutdown()
