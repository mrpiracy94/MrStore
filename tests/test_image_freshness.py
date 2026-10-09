"""Deterministic tests for image build age — never require registry access."""
from datetime import datetime, timezone
import json
import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from image_freshness import examine, analyze, parse_created, summarize  # noqa: E402

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def ok(timestamp=None, labels=None):
    data = {"created": timestamp, "config": {"Labels": labels or {}}}
    return subprocess.CompletedProcess(["crane"], 0, json.dumps(data), "")


class ImageBuildFreshnessTests(unittest.TestCase):
    def test_parse_created_rejects_missing_or_ambiguous_dates(self):
        self.assertIsNone(parse_created(None))
        self.assertIsNone(parse_created("2026-10-09T03:00:00"))
        self.assertIsNone(parse_created("not-a-date"))
        self.assertEqual(parse_created("2026-10-09T03:00:00Z"),
                         datetime(2026, 10, 9, 3, tzinfo=timezone.utc))

    def test_old_build_is_a_review_flag_not_an_upstream_abandonment_claim(self):
        runner = Mock(return_value=ok("2024-01-01T00:00:00Z"))
        entry = examine("example/image:1", ["app/service"], NOW,
                        runner=runner)
        self.assertEqual(entry["status"], "build_365_plus")
        self.assertGreaterEqual(entry["build_age_days"], 365)
        self.assertEqual(entry["reference"], "tag")
        self.assertEqual(entry["platform"], "linux/amd64")
        self.assertEqual(runner.call_args.args[0][:4],
                         ["crane", "config", "--platform", "linux/amd64"])

    def test_immutable_digest_is_not_silently_called_unmaintained(self):
        ref = "example/app:1@sha256:" + "a" * 64
        entry = examine(ref, ["my-app/service"], NOW,
                        runner=Mock(return_value=ok("2026-09-01T00:00:00Z")))
        self.assertEqual(entry["status"], "build_under_180")
        self.assertEqual(entry["reference"], "immutable")

    def test_oci_label_fallback_and_no_label(self):
        value = ok(None, {"org.opencontainers.image.created": "2026-01-01T00:00:00Z"})
        entry = examine("app:test", [], NOW, runner=Mock(return_value=value))
        self.assertEqual(entry["status"], "build_180_364")
        self.assertEqual(entry["timestamp_source"], "oci_label")
        none = examine("app:missing", [], NOW, runner=Mock(return_value=ok()))
        self.assertEqual(none["status"], "unknown")
        self.assertIsNone(none["build_age_days"])

    def test_error_never_counts_as_an_up_to_date_app(self):
        bad = subprocess.CompletedProcess(["crane"], 1, "", "MANIFEST_UNKNOWN")
        runner = Mock(return_value=bad)
        entry = examine("app:missing", [], NOW, runner=runner)
        self.assertEqual(entry["status"], "error")
        self.assertIn("MANIFEST_UNKNOWN", entry["error"])
        runner.assert_called_once()

    def test_transient_rate_limit_retried_but_still_never_suppressed(self):
        bad = subprocess.CompletedProcess(["crane"], 1, "", "TOOMANYREQUESTS")
        runner = Mock(side_effect=[bad, ok("2026-09-01T00:00:00Z")])
        wait = Mock()
        entry = examine("app:tag", [], NOW, runner=runner, sleeper=wait)
        self.assertEqual(entry["status"], "build_under_180")
        self.assertEqual(runner.call_count, 2)
        wait.assert_called_once_with(5)

        runner = Mock(return_value=bad)
        entry = examine("app:tag", [], NOW, runner=runner, sleeper=Mock())
        self.assertEqual(entry["status"], "error")
        self.assertEqual(runner.call_count, 2)

    def test_upstream_retirement_is_explicit_even_if_registry_fails(self):
        runner = Mock(return_value=subprocess.CompletedProcess(
            ["crane"], 1, "", "manifest does not contain linux/amd64"))
        entry = examine("lscr.io/linuxserver/steamos:latest", ["steamos/steamos"],
                        NOW, runner=runner)
        self.assertEqual(entry["status"], "error")
        self.assertIn("2025-12-13-steamosdep", entry["upstream_deprecation"])

    def test_cops_upstream_abandonment_documented(self):
        bad = subprocess.CompletedProcess(["crane"], 1, "", "unknown manifest")
        entry = examine("lscr.io/linuxserver/cops:latest",
                        ["cops/cops"], NOW, runner=Mock(return_value=bad))
        self.assertEqual(entry["status"], "error")
        self.assertIn("2023-05-15-cops", entry["upstream_deprecation"])

    def test_shard_coverage_and_summary(self):
        def inspect(ref, usage, now):
            return {"image": ref, "apps": usage, "status": "build_under_180",
                    "build_age_days": 1, "reference": "tag", "error": None}
        usage = {f"example/app{i}:latest": ["foo/bar"] for i in range(21)}
        reports = [analyze(usage, s, 4, now=NOW, inspector=inspect) for s in range(4)]
        images = [item["image"] for r in reports for item in r["results"]]
        self.assertEqual(len(images), len(set(images)))
        self.assertEqual(sorted(images), sorted(usage))
        self.assertIn("não", summarize(reports[0]).lower())

    def test_schedule_does_not_claim_age_proves_deprecation(self):
        workflow = (ROOT / ".github/workflows/image-freshness.yml").read_text()
        self.assertIn("matrix:", workflow)
        self.assertIn("shard: [0, 1, 2, 3, 4, 5, 6, 7]", workflow)
        self.assertIn("scripts/image_freshness.py", workflow)


if __name__ == "__main__":
    unittest.main()
