import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "scripts/run-unit-tests.py"


class CiRunnerTests(unittest.TestCase):
    def run_fixture(self, source, *, module="test_example", allow=False):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, f"{module}.py").write_text(
                textwrap.dedent(source), encoding="utf-8"
            )
            command = [sys.executable, str(RUNNER), directory]
            if allow:
                command.append("--allow-missing-clients")
            # Do not let the parent suite's discovery directory leak into fixtures.
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            return subprocess.run(
                command, check=False, capture_output=True, text=True, env=environment
            )

    def test_successful_suite(self):
        result = self.run_fixture("""
            import unittest
            class Example(unittest.TestCase):
                def test_ok(self):
                    self.assertEqual(2 + 2, 4)
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failures_errors_and_unexpected_skips_fail(self):
        for body, diagnostic in (
            ("self.fail('fixture failure')", "FAILED (failures=1)"),
            ("raise RuntimeError('fixture error')", "FAILED (errors=1)"),
            ("self.skipTest('missing fixture')", "Unexpected skip:"),
        ):
            with self.subTest(body=body):
                result = self.run_fixture(
                    "import unittest\nclass Example(unittest.TestCase):\n"
                    f"    def test_example(self):\n        {body}\n",
                    allow=True,
                )
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertIn(diagnostic, result.stderr)

    def test_empty_suite_fails(self):
        result = self.run_fixture("", allow=True)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("No tests discovered", result.stderr)

    def test_missing_client_allowlist_requires_matching_id_and_reason(self):
        for module, class_name, method, reason in (
            (
                "test_atlassian_mcp_startup",
                "InstalledClientTests",
                "test_codex_accepts_managed_override_after_conflicting_cli_value",
                "Codex is not installed",
            ),
            (
                "test_atlassian_mcp_startup",
                "InstalledClientTests",
                "test_opencode_runtime_override_wins_over_image_and_inline_settings",
                "OpenCode is not installed",
            ),
            (
                "test_atlassian_mcp_startup",
                "InstalledClientTests",
                "test_opencode_runtime_override_wins_over_image_and_inline_settings",
                "OpenCode v2 is not installed",
            ),
            (
                "test_atlassian_mcp_startup",
                "InstalledClientTests",
                "test_claude_connects_when_enabled_and_blocks_project_entry_when_disabled",
                "Claude Code is not installed",
            ),
            (
                "test_codex_auth_startup",
                "CodexAuthStartupTests",
                "test_installed_codex_caches_and_refreshes_provider_placeholder",
                "Codex is not installed",
            ),
            (
                "test_skills",
                "SkillTests",
                "test_installed_claude_discovers_skill_through_directory_symlink",
                "Claude Code is not installed",
            ),
        ):
            with self.subTest(module=module, method=method, reason=reason):
                source = (
                    f"import unittest\nclass {class_name}(unittest.TestCase):\n"
                    f"    def {method}(self):\n        self.skipTest({reason!r})\n"
                )
                result = self.run_fixture(source, module=module, allow=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                strict = self.run_fixture(source, module=module)
                self.assertNotEqual(strict.returncode, 0, strict.stderr)
                wrong_reason = self.run_fixture(
                    source.replace(reason, "writable /workspace is required"),
                    module=module,
                    allow=True,
                )
                self.assertNotEqual(wrong_reason.returncode, 0, wrong_reason.stderr)
                wrong_id = self.run_fixture(source, allow=True)
                self.assertNotEqual(wrong_id.returncode, 0, wrong_id.stderr)
