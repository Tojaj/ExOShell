import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_versions.py"
spec = importlib.util.spec_from_file_location("check_versions", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CheckerTests(unittest.TestCase):
    def test_pin_discovery_covers_dockerfile(self):
        self.assertEqual(set(checker.parse_pins()), set(checker.PINS))
        self.assertEqual(len(checker.PINS), 12)

    def test_stable_filter_and_lag(self):
        versions = ["v1.2.0", "v1.3.0-rc.1", "v1.1.0", "v1.3.0"]
        self.assertEqual(checker.selected(versions, 0), "v1.3.0")
        self.assertEqual(checker.selected(versions, 1), "v1.2.0")
        self.assertEqual(checker.selected(versions, 2), "v1.1.0")
        with self.assertRaises(LookupError):
            checker.selected(versions, 3)

    def test_github_missing_asset_preserves_candidate_and_blocks_upgrade(self):
        release = {"tag_name": "v1.4.0", "draft": False, "prerelease": False,
                   "published_at": "2026-09-20T00:00:00Z",
                   "assets": [{"name": "oras_1.4.0_linux_amd64.tar.gz"}]}
        row = checker.check("ORAS_VERSION", "1.3.0", 0, lambda *a, **k: [release])
        self.assertEqual(row["candidate"], "1.4.0")
        self.assertEqual(row["status"], "error")
        self.assertIn("arm64", row["note"])

    def test_draft_and_prerelease_are_ignored(self):
        releases = [
            {"tag_name": "v1.6.0", "draft": True},
            {"tag_name": "v1.5.0", "prerelease": True},
            {"tag_name": "v1.4.0", "assets": [{"name": "yq_linux_amd64"}, {"name": "yq_linux_arm64"}]},
        ]
        row = checker.check("YQ_VERSION", "1.3.0", 0, lambda *a, **k: releases)
        self.assertEqual((row["candidate"], row["status"]), ("1.4.0", "upgrade"))

    def test_partial_network_failure_never_infers_upgrade(self):
        def denied(*args, **kwargs):
            raise LookupError("policy_denied")
        row = checker.check("GWS_VERSION", "0.22.5", 0, denied)
        self.assertIsNone(row["candidate"])
        self.assertEqual(row["status"], "error")
        self.assertIn("policy_denied", row["note"])
        self.assertIn("registry.npmjs.org", row["source"])

    def test_npm_latest_tag_caps_candidates_and_uses_publish_date(self):
        def package(version):
            return {"bin": {"gws": "run.js"}, "dist": {"tarball": f"https://example.test/{version}.tgz"}}
        metadata = {"dist-tags": {"latest": "1.2.0"}, "versions": {
            "1.1.0": package("1.1.0"), "1.2.0": package("1.2.0"), "1.3.0": package("1.3.0")},
            "time": {"1.2.0": "2026-09-20T00:00:00Z"}}
        current = checker.check("GWS_VERSION", "1.1.0", 0, lambda *a, **k: metadata)
        self.assertEqual((current["candidate"], current["date"]), ("1.2.0", "2026-09-20T00:00:00Z"))
        lagged = checker.check("GWS_VERSION", "1.1.0", 1, lambda *a, **k: metadata)
        self.assertEqual(lagged["candidate"], "1.1.0")

    def test_no_downgrade_and_claude_lag(self):
        def native(url, **kwargs):
            if url.endswith("/stable"):
                return "2.1.277"
            return {"version": "2.1.277", "buildDate": "2026-09-18", "platforms": {"linux-x64": {}, "linux-arm64": {}}}
        row = checker.check("CLAUDE_VERSION", "2.1.283", 0, native)
        self.assertEqual(row["status"], "ahead; no downgrade")
        lagged = checker.check("CLAUDE_VERSION", "2.1.283", 1, native)
        self.assertEqual(lagged["status"], "error")
        self.assertIn("lagged", lagged["note"])

    def test_oc_stays_in_pinned_stream(self):
        def source(url, **kwargs):
            if url.endswith("/channels"):
                return [{"name": "stable-4.15.yaml"}, {"name": "stable-4.16.yaml"}]
            if url.endswith("stable-4.15.yaml"):
                return "name: stable-4.15\nversions:\n- 4.14.99\n- 4.15.1\n- 4.15.2\n"
            return True
        row = checker.check("OC_VERSION", "4.15.0", 0, source)
        self.assertEqual((row["candidate"], row["status"]), ("4.15.2", "upgrade"))
        self.assertIn("4.16", row["note"])

    def test_oc_mirror_failure_preserves_candidate(self):
        def source(url, **kwargs):
            if url.endswith("/channels"):
                return [{"name": "stable-4.15.yaml"}]
            if url.endswith("stable-4.15.yaml"):
                return "versions:\n- 4.15.2\n"
            raise LookupError("policy_denied")
        row = checker.check("OC_VERSION", "4.15.0", 0, source)
        self.assertEqual(row["candidate"], "4.15.2")
        self.assertEqual(row["status"], "error")
        self.assertIn("policy_denied", row["note"])


if __name__ == "__main__":
    unittest.main()
