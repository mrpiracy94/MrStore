"""Fail-closed application quarantine from complete independent multiarch scans.

Only the working tree of the CI runner is filtered; source manifests and users'
installed containers are never modified. A scan error excludes every app using
the affected image, and every result remains in GitHub Actions artifacts.
"""
import argparse
import json
import re
from pathlib import Path
import shutil
import yaml

from catalog import ROOT, apps, image_usage
from cves import shard_images
from release_security import declared_platforms
from privilege_policy import risky_settings

SEVERITIES = {"HIGH", "CRITICAL"}


def decide(root, reports):
    items = apps(root)
    usage = image_usage(items)
    expected = declared_platforms(items)
    if set(expected) != set(usage):
        raise ValueError("Mismatch between manifest images and architecture inventory")
    image_checks = {}
    pinned_images = {}
    n_shards = 8
    if len(reports) != n_shards:
        raise ValueError(f"Expected {n_shards} independent scan reports; got {len(reports)}")
    seen_shards = set()
    for path in reports:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        shard = report.get("shard")
        if report.get("schema") != 1 or report.get("shards") != n_shards or (
            type(shard) is not int or shard not in range(n_shards)
        ) or report.get("images_total") != len(usage) or shard in seen_shards:
            raise ValueError(f"Invalid/duplicate scan shard: {path}")
        seen_shards.add(shard)
        rows = report.get("results")
        if not isinstance(rows, list) or [r.get("image") for r in rows] != (
            shard_images(usage, shard, n_shards)
        ):
            raise ValueError(f"Missing, duplicate or unexpected images: {path}")
        for row in rows:
            image = row["image"]
            checks = row.get("checks")
            if not isinstance(checks, list) or [
                c.get("arch") for c in checks
            ] != expected[image]:
                raise ValueError(f"Missing or unexpected architecture check: {image}")
            for check in checks:
                if check.get("status") not in ("ok", "error") or not isinstance(
                    check.get("findings"), list
                ) or (check["status"] == "error" and not check.get("error")) or (
                    check["status"] == "ok" and check.get("error")
                ):
                    raise ValueError(f"Incomplete/malformed scan result: {image}")
                if any(not isinstance(hit, dict) or
                       hit.get("severity") not in SEVERITIES
                       for hit in check["findings"]):
                    raise ValueError(f"Malformed CVE findings: {image}")
            if image in image_checks:
                raise ValueError(f"Duplicate image check: {image}")
            pinned = row.get("pinned")
            if pinned is not None and (not isinstance(pinned, str) or
                                      not re.fullmatch(r".+@sha256:[0-9a-f]{64}", pinned)):
                raise ValueError(f"Image digest is not immutable: {image}")
            if pinned is None and not all(c["status"] == "error" for c in checks):
                raise ValueError(f"Unpinned image was approved: {image}")
            image_checks[image] = checks
            pinned_images[image] = pinned
    if set(image_checks) != set(usage):
        raise ValueError("Incomplete image coverage; cannot publish")

    rejected = {}
    for image, checks in image_checks.items():
        problems = []
        for check in checks:
            if check["status"] == "error":
                problems.append(f"{check['arch']}: inconclusive ({check['error']})")
            if check["findings"]:
                counts = {sev: sum(x["severity"] == sev for x in check["findings"])
                          for sev in SEVERITIES}
                problems.append(f"{check['arch']}: {counts['CRITICAL']} CRITICAL, "
                                f"{counts['HIGH']} HIGH")
        if not pinned_images[image]:
            problems.append("missing immutable digest")
        if problems:
            rejected[image] = problems

    clean, quarantined = [], {}
    for app in items:
        app_images = sorted({service["image"] for service in app.source["services"].values()})
        reasons = {image: rejected[image] for image in app_images if image in rejected}
        unsafe = risky_settings(app.source)
        if unsafe:
            reasons["unsafe Compose permissions"] = [
                f"{service}: {flag}={value}" for service, flag, value in sorted(unsafe)
            ]
        if reasons:
            quarantined[app.folder] = reasons
        else:
            clean.append(app.folder)
    return {
        "source_apps": len(items),
        "source_images": len(usage),
        "approved_apps": sorted(clean),
        "quarantined_apps": quarantined,
        "blocked_images": len(rejected),
        "pinned_images": {image: pinned_images[image] for image in sorted(usage)
                          if image not in rejected},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "out/quarantine.json")
    parser.add_argument("--summary", type=Path, default=ROOT / "out/quarantine.md")
    parser.add_argument("--apply", action="store_true",
                        help="Remove quarantined Apps/ folders in CI checkout only")
    args = parser.parse_args()
    paths = sorted(args.reports_dir.glob("release-security-*.json"))
    decision = decide(args.root, paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# MrStore — quarantined applications",
        "",
        f"- Source applications: {decision['source_apps']}",
        f"- Approved applications: {len(decision['approved_apps'])}",
        f"- Quarantined applications: {len(decision['quarantined_apps'])}",
        f"- Images with HIGH/CRITICAL or incomplete checks: {decision['blocked_images']}",
        "",
        "Both declared architectures must pass. CVEs, scan errors, and unsafe Compose privileges are quarantined.",
        "Approved images are pinned to the exact scanned manifest digests in the published catalog.",
        "Installed ZimaOS apps are not modified. Full per-image findings are in scan artifacts.",
        "",
    ]
    for app, images in sorted(decision["quarantined_apps"].items()):
        lines.append(f"## {app}")
        for image, reasons in images.items():
            lines.append(f"- `{image}`: {'; '.join(reasons)}")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    if not decision["approved_apps"]:
        raise ValueError("No approved applications: refusing to overwrite the live catalog")
    if args.apply:
        for folder in decision["approved_apps"]:
            path = args.root / "Apps" / folder / "docker-compose.yml"
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            for spec in manifest["services"].values():
                spec["image"] = decision["pinned_images"][spec["image"]]
            path.write_text(yaml.safe_dump(manifest, sort_keys=False,
                                           allow_unicode=True), encoding="utf-8")
        for folder in decision["quarantined_apps"]:
            target = args.root / "Apps" / folder
            if not target.is_dir() or target.is_symlink():
                raise ValueError(f"Unexpected app path, refusing to remove: {target}")
            shutil.rmtree(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
