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

    def test_opencode_site_forwards_opaque_placeholders_without_body_rewrite(self) -> None:
        site = self.network["opencode_site"]
        self.assertEqual(site["endpoints"], [{
            "host": "opencode.ai",
            "port": 443,
            "protocol": "rest",
            "enforcement": "audit",
            "access": "full",
            "allow_uninspected_credentials": True,
        }])
        self.assertEqual(site["binaries"], self.network["opencode_model_catalog"]["binaries"])
        self.assertIn(
            {"path": "/usr/lib/node_modules/@opencode/cli/bin/opencode.exe"},
            site["binaries"],
        )

    def test_body_scanning_exception_does_not_extend_to_other_baseline_hosts(self) -> None:
        for name, policy in self.network.items():
            if name == "opencode_site":
                continue
            for endpoint in policy["endpoints"]:
                with self.subTest(policy=name, host=endpoint["host"]):
                    self.assertFalse(endpoint.get("allow_uninspected_credentials", False))
                    self.assertFalse(endpoint.get("request_body_credential_rewrite", False))

    def test_other_opencode_inference_backends_keep_opaque_placeholders(self) -> None:
        for backend in ("openai", "anthropic", "openrouter"):
            with self.subTest(backend=backend):
                profile = yaml.safe_load(
                    (ROOT / f"provider-profiles/provider-opencode-{backend}.yaml").read_text()
                )
                for endpoint in profile["endpoints"]:
                    self.assertIs(endpoint.get("allow_uninspected_credentials"), True)
                    self.assertFalse(endpoint.get("request_body_credential_rewrite", False))


if __name__ == "__main__":
    unittest.main()
