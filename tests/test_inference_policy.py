from __future__ import annotations

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class InferencePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = yaml.safe_load(
            (ROOT / "policies/policy.yaml").read_text()
        )["network_policies"]

    def test_opencode_site_uses_native_body_classification(self) -> None:
        site = self.network["opencode_site"]
        self.assertEqual(site["endpoints"], [{
            "host": "opencode.ai",
            "port": 443,
            "protocol": "rest",
            "enforcement": "audit",
            "access": "full",
        }])
        self.assertEqual(site["binaries"], self.network["opencode_model_catalog"]["binaries"])
        self.assertIn(
            {"path": "/usr/lib/node_modules/@opencode/cli/bin/opencode.exe"},
            site["binaries"],
        )

    def test_baseline_keeps_body_classification_and_disables_body_rewrite(self) -> None:
        for name, policy in self.network.items():
            for endpoint in policy["endpoints"]:
                with self.subTest(policy=name, host=endpoint["host"]):
                    self.assertFalse(endpoint.get("allow_uninspected_credentials", False))
                    self.assertFalse(endpoint.get("request_body_credential_rewrite", False))

    def test_inference_profiles_use_native_classification_without_body_rewrite(self) -> None:
        for name in ("codex-cli", "claude-code-cli", "opencode-openai",
                     "opencode-anthropic", "opencode-openrouter"):
            with self.subTest(profile=name):
                profile = yaml.safe_load(
                    (ROOT / f"provider-profiles/provider-{name}.yaml").read_text()
                )
                for endpoint in profile["endpoints"]:
                    self.assertFalse(endpoint.get("allow_uninspected_credentials", False))
                    self.assertFalse(endpoint.get("request_body_credential_rewrite", False))


if __name__ == "__main__":
    unittest.main()
