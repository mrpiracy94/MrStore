"""Online audit of external storefront artwork. Never execute manifests or download full images."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import json
from pathlib import Path
import socket
import urllib.error
import urllib.parse
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[1]
OWN_RAW_PREFIX = "https://raw.githubusercontent.com/mrpiracy94/MrStore/main/"
GOOD_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a",
              b"RIFF", b"\x00\x00\x01\x00")


def is_image(data: bytes, content_type: str) -> bool:
    value = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return True
    if any(data.startswith(sig) for sig in GOOD_MAGIC if sig != b"RIFF"):
        return True
    return ("svg" in content_type or value.startswith((b"<svg", b"<?xml"))) and (
        b"<svg" in value[:512])


def ensure_public_https(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only anonymous HTTPS public resources are accepted")
    if parsed.port not in (None, 443):
        raise ValueError("Non-standard HTTPS ports are not allowed")
    host = parsed.hostname
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise OSError(f"DNS lookup failed: {exc}") from exc
    if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global
                            for entry in addresses):
        raise ValueError("Non-public DNS address blocked")


class PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        ensure_public_https(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def check_url(url: str, timeout: float = 8.0) -> dict:
    try:
        ensure_public_https(url)
        opener = urllib.request.build_opener(PublicRedirects())
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "MrStore-artwork-audit/1.0",
                     "Accept": "image/avif,image/webp,image/png,image/jpeg,image/svg+xml,image/*"},
            method="GET")
        with opener.open(request, timeout=timeout) as response:
            data = response.read(512)
            mimetype = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if not is_image(data, mimetype):
                return {"status": "broken", "reason": "URL did not return recognizable image data",
                        "http_status": response.status, "content_type": mimetype}
            return {"status": "ok", "http_status": response.status, "content_type": mimetype}
    except ValueError as exc:
        return {"status": "unsafe", "reason": str(exc)}
    except urllib.error.HTTPError as exc:
        # 401/403/429 and 5xx may be transient or protected by the upstream CDN.
        status = "broken" if exc.code in (404, 410) else "inconclusive"
        return {"status": status, "http_status": exc.code, "reason": str(exc)}
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        return {"status": "inconclusive", "reason": str(exc)[:240]}


def collect(root: Path) -> dict[str, list[str]]:
    refs = defaultdict(list)
    store = json.loads((root / "store-config.json").read_text(encoding="utf-8"))
    refs[store.get("icon", "")].append("store-config.json:icon")
    for path in sorted((root / "Apps").glob("*/docker-compose.yml")):
        obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        metadata = obj.get("x-casaos") or {}
        for field in ("icon", "thumbnail"):
            refs[metadata.get(field, "")].append(f"{path.relative_to(root)}:{field}")
    return dict(refs)


def audit(root: Path = ROOT, workers: int = 12, timeout: float = 8.0,
          defer_unpublished: bool = False) -> dict:
    refs = collect(root)
    results = {}
    pending = {}
    for url in refs:
        if not isinstance(url, str) or not url.startswith("https://"):
            results[url] = {"status": "unsafe", "reason": "Missing HTTPS asset URL"}
        elif defer_unpublished and url.startswith(OWN_RAW_PREFIX):
            rel = urllib.parse.urlsplit(url).path.split("/main/", 1)[-1]
            local = root / rel
            if local.is_file():
                # Do not pretend that a PR-only asset is already online on main.
                pending[url] = {"status": "deferred", "reason": "Local file exists; main URL needs post-merge verification"}
            else:
                results[url] = {"status": "broken", "reason": f"Missing tracked local file: {rel}"}
    results.update(pending)
    targets = [url for url in refs if url not in results]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_url, url, timeout): url for url in targets}
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception as exc:
                results[url] = {"status": "inconclusive", "reason": str(exc)[:240]}
    entries = [{"url": url, "references": refs[url], **results[url]}
               for url in sorted(refs)]
    counts = dict(Counter(entry["status"] for entry in entries))
    return {"references": sum(map(len, refs.values())), "unique_urls": len(refs),
            "counts": counts, "results": entries,
            "complete": counts.get("inconclusive", 0) == 0 and counts.get("deferred", 0) == 0,
            "note": "A successful HTTP asset response does not prove rendering on real ZimaOS."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--strict", action="store_true",
                        help="Fail on unsafe or definitively broken artwork.")
    parser.add_argument("--require-complete", action="store_true",
                        help="Additionally fail on transient/inconclusive or deferred checks.")
    parser.add_argument("--defer-unpublished", action="store_true",
                        help="For pull requests only: flag valid local main assets as deferred.")
    options = parser.parse_args()
    if not 1 <= options.workers <= 32 or not 1 <= options.timeout <= 30:
        parser.error("workers must be 1..32 and timeout 1..30 seconds")
    report = audit(options.root, options.workers, options.timeout, options.defer_unpublished)
    output = options.root / "out"
    output.mkdir(parents=True, exist_ok=True)
    (output / "asset-audit-online.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Online storefront artwork audit", "",
             f"References: {report['references']}; unique URLs: {report['unique_urls']}", "",
             "| Result | URLs |", "| --- | ---: |"]
    for key in ("ok", "broken", "unsafe", "inconclusive", "deferred"):
        lines.append(f"| {key} | {report['counts'].get(key, 0)} |")
    for entry in report["results"]:
        if entry["status"] not in ("ok", "deferred"):
            lines.append(f"- **{entry['status']}** \u2014 {entry['url']} "
                         f"({', '.join(entry['references'][:5])}): {entry.get('reason', '')}")
    lines.extend(["", report["note"], ""])
    (output / "asset-audit-online.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"unique_urls": report["unique_urls"], "counts": report["counts"],
                      "complete": report["complete"]}, indent=2))
    if options.strict and (report["counts"].get("broken", 0) or report["counts"].get("unsafe", 0)):
        return 1
    return int(options.require_complete and not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
