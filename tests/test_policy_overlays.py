from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "policy-overlays"))
import apply as policy_apply  # noqa: E402


def endpoint(host: str, path: str, **extra: object) -> dict[str, object]:
    return {"host": host, "port": 443, "path": path, "protocol": "graphql", **extra}


class OverlayResolutionTests(unittest.TestCase):
    def test_resolves_bare_name_and_explicit_path(self) -> None:
        self.assertEqual(
            policy_apply.resolve_overlay("github-push"),
            ROOT / "policy-overlays" / "github-push.yaml",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "custom.yaml"
            path.write_text("network_policies: {}\n")
            self.assertEqual(policy_apply.resolve_overlay(str(path)), path)


class ExternalPolicyIntegrationTests(unittest.TestCase):
    def test_explicit_baseline_and_overlay_preserve_live_static_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            live = {
                "filesystem_policy": {"read_write": ["/workspace", "/live-only"]},
                "landlock": {"compatibility": "best_effort"},
                "process": {"run_as_user": "sandbox"},
                "network_policies": {"old_session_grant": {"endpoints": []}},
            }
            live_file = directory / "live.json"
            live_file.write_text(json.dumps({"policy": live}))
            baseline_file = directory / "baseline.yaml"
            baseline_file.write_text(yaml.safe_dump({
                "filesystem_policy": {"read_write": ["/different"]},
                "network_policies": {"base": {"endpoints": []}},
            }))
            overlay_file = directory / "external-overlay.yaml"
            overlay_file.write_text("network_policies:\n  extra: {endpoints: []}\n")
            binary = directory / "openshell"
            binary.write_text(
                '#!/usr/bin/env bash\nset -euo pipefail\n'
                '[[ "$*" == "policy get test --base -o json" ]]\n'
                'cat "$LIVE_POLICY"\n'
            )
            binary.chmod(0o755)
            environment = {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}",
                           "LIVE_POLICY": str(live_file)}
            result = subprocess.run(
                [sys.executable, str(ROOT / "policy-overlays/apply.py"),
                 "--sandbox", "test", "--base-file", str(baseline_file),
                 "--revert", "--dry-run", str(overlay_file)],
                cwd=directory, env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            final = yaml.safe_load(result.stdout)
            self.assertEqual(set(final["network_policies"]), {"base", "extra"})
            for key in ("filesystem_policy", "landlock", "process"):
                self.assertEqual(final[key], live[key])


class OverlayCompositionTests(unittest.TestCase):
    def test_collision_replaces_complete_entry(self) -> None:
        base = {
            "service": {
                "name": "old",
                "endpoints": [{"host": "old.example.com"}],
                "binaries": [{"path": "/usr/bin/old"}],
                "future_sensitive_field": "must not survive",
            }
        }
        replacement = {"service": {"endpoints": [{"host": "new.example.com"}]}}
        composed = policy_apply.compose_network_policies(base, [(Path("replacement.yaml"), replacement)])
        self.assertEqual(composed["service"], replacement["service"])

    def test_distinct_entries_compose(self) -> None:
        base = {"base": {"endpoints": []}}
        overlay = {"extra": {"binaries": []}}
        composed = policy_apply.compose_network_policies(base, [(Path("extra.yaml"), overlay)])
        self.assertEqual(set(composed), {"base", "extra"})

    def test_duplicate_overlay_key_is_rejected(self) -> None:
        overlays = [
            (Path("first.yaml"), {"same": {}}),
            (Path("second.yaml"), {"same": {}}),
        ]
        with self.assertRaisesRegex(policy_apply.PolicyError, "appears in both"):
            policy_apply.compose_network_policies({}, overlays)

    def test_gitlab_only_composition_does_not_require_github(self) -> None:
        base = {"gitlab": {"endpoints": [endpoint("gitlab.com", "/api/graphql")]}}
        policy_apply.validate_invariants(policy_apply.compose_network_policies(base, []))

    def test_host_specific_gitlab_overlay_replaces_its_matching_baseline_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            base_path = directory / "policy.yaml"
            base_path.write_text(
                "network_policies:\n  gitlab_example_graphql:\n"
                "    endpoints:\n      - host: gitlab.example.com\n"
                "        port: 443\n        path: /api/graphql\n"
                "        protocol: graphql\n        access: read-only\n"
            )
            overlay_path = directory / "overlay.yaml"
            overlay_path.write_text(
                "network_policies:\n  gitlab_example_graphql:\n"
                "    endpoints:\n      - host: gitlab.example.com\n"
                "        port: 443\n        path: /api/graphql\n"
                "        protocol: graphql\n"
                "        rules:\n          - allow: {operation_type: query}\n"
            )
            base = policy_apply.load_base_network_policies(base_path)
            resolved = policy_apply.resolve_overlay(str(overlay_path))
            overlay = policy_apply.load_overlay(resolved)
            composed = policy_apply.compose_network_policies(base, [(resolved, overlay)])
            self.assertEqual(composed["gitlab_example_graphql"], overlay["gitlab_example_graphql"])
            policy_apply.validate_invariants(composed)

    def test_revert_diff_compares_live_state_to_final_state(self) -> None:
        live = {"base": {}, "active_overlay": {}}
        final = {"base": {}}
        self.assertEqual(policy_apply.summarise_diff(live, final), ["  - active_overlay"])


class OverlayValidationTests(unittest.TestCase):
    def write_overlay(self, content: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "overlay.yaml"
        path.write_text(content)
        return path

    def test_duplicate_yaml_keys_are_rejected(self) -> None:
        path = self.write_overlay("network_policies:\n  service: {}\n  service: {}\n")
        with self.assertRaisesRegex(policy_apply.PolicyError, "duplicate YAML key 'service'"):
            policy_apply.load_overlay(path)

    def test_malformed_overlay_shapes_are_rejected(self) -> None:
        cases = {
            "non-mapping-root": "- network_policies\n",
            "extra-root-key": "network_policies: {}\nother: {}\n",
            "non-mapping-policies": "network_policies: []\n",
            "non-mapping-entry": "network_policies:\n  service: []\n",
            "non-list-endpoints": "network_policies:\n  service:\n    endpoints: {}\n",
            "non-list-binaries": "network_policies:\n  service:\n    binaries: {}\n",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(policy_apply.PolicyError):
                    policy_apply.load_overlay(self.write_overlay(content))

    def test_reserved_policy_key_is_rejected(self) -> None:
        path = self.write_overlay("network_policies:\n  _provider_api: {}\n")
        with self.assertRaisesRegex(policy_apply.PolicyError, "reserved policy keys"):
            policy_apply.load_overlay(path)

    def test_non_string_policy_key_is_rejected(self) -> None:
        path = self.write_overlay("network_policies:\n  7: {}\n")
        with self.assertRaisesRegex(policy_apply.PolicyError, "keys must be strings"):
            policy_apply.load_overlay(path)

    def test_access_and_rules_are_mutually_exclusive(self) -> None:
        policies = {
            "service": {
                "endpoints": [{"host": "example.com", "access": "read-only", "rules": []}]
            }
        }
        with self.assertRaisesRegex(policy_apply.PolicyError, "mutually exclusive"):
            policy_apply.validate_invariants(policies)

    def test_duplicate_graphql_selectors_are_rejected(self) -> None:
        github_ports = {
            "host": "api.github.com",
            "ports": [443],
            "path": "/graphql",
            "protocol": "graphql",
        }
        cases = {
            "github": {
                "first": {"endpoints": [endpoint("api.github.com", "/graphql")]},
                "second": {"endpoints": [github_ports]},
            },
            "gitlab-per-host": {
                "first": {"endpoints": [endpoint("gitlab.com", "/api/graphql")]},
                "second": {"endpoints": [endpoint("gitlab.com", "/api/graphql")]},
            },
        }
        for name, policies in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(policy_apply.PolicyError, "duplicate GraphQL selector"):
                    policy_apply.validate_invariants(policies)


if __name__ == "__main__":
    unittest.main()
