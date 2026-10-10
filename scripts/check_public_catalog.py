"""Verify the public MrStore ZimaOS v2 catalog without installing anything."""
import argparse
import json
from urllib.request import Request, urlopen


def fetch_json(url, timeout=15):
    req = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    with urlopen(req, timeout=timeout) as result:
        if result.status != 200:
            raise ValueError(f"HTTP {result.status}: {url}")
        obj = json.load(result)
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {url}")
    return obj


def verify_live(base, fetcher=fetch_json):
    base = base.rstrip("/")
    store = fetcher(base + "/store.json")
    index = fetcher(base + "/index.json")
    release = fetcher(base + "/release-status.json")
    if store.get("version") != 2 or index.get("version") != 2:
        raise ValueError("Incorrect ZimaOS v2 protocol")
    entries = index.get("apps")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Public index has no apps")
    ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    if len(ids) != len(entries) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Invalid app entry or ID")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate app ID")
    approved = len(entries)
    source_count = release.get("source_apps")
    approved_count = release.get("approved_count")
    quarantined_count = release.get("quarantined_count")
    if any(type(x) is not int or x < 0 for x in
           (source_count, approved_count, quarantined_count)):
        raise ValueError("Missing or invalid published quarantine counts")
    if source_count != approved_count + quarantined_count:
        raise ValueError("Inconsistent source/approved/quarantined totals")
    if index.get("app_count") != approved or approved_count != approved:
        raise ValueError("Approved count does not match published index")
    allowed = release.get("approved")
    quarantined = release.get("quarantined")
    if not isinstance(allowed, list) or not isinstance(quarantined, dict):
        raise ValueError("Missing approval/quarantine evidence")
    if len(allowed) != approved or len(quarantined) != quarantined_count:
        raise ValueError("Security evidence does not match the catalog")
    # Counts alone are not sufficient: a report for a different selection can
    # have exactly the same length as the public index. Require identity too.
    prefix = "io.github.mrpiracy94."
    if (not all(isinstance(slug, str) and slug and
                slug.isascii() and
                all(ch.islower() or ch.isdigit() or ch in "._-" for ch in slug)
                for slug in allowed)
            or len(set(allowed)) != len(allowed)):
        raise ValueError("Invalid or duplicate approved application slugs")
    expected = {prefix + slug for slug in allowed}
    if set(ids) != expected:
        raise ValueError("Published app IDs differ from the approved CVE selection")
    if set(quarantined).intersection(allowed):
        raise ValueError("An application is both approved and quarantined")
    return {"approved": approved, "quarantined": quarantined_count, "total": source_count}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://mrpiracy94.github.io/MrStore")
    args = p.parse_args()
    print("MrStore public catalog:", verify_live(args.base))


if __name__ == "__main__":
    main()
