"""Run a unittest suite, rejecting empty suites and unexpected skips."""

import argparse
import sys
import unittest

# Review changes alongside the installed-client tests. A skip for any other
# reason (including a missing writable workspace) remains a failure.
MISSING_CLIENT_SKIPS = {
    "test_atlassian_mcp_startup.InstalledClientTests."
    "test_codex_accepts_managed_override_after_conflicting_cli_value": {
        "Codex is not installed"
    },
    "test_atlassian_mcp_startup.InstalledClientTests."
    "test_opencode_runtime_override_wins_over_image_and_inline_settings": {
        "OpenCode is not installed",
        "OpenCode v2 is not installed",
    },
    "test_atlassian_mcp_startup.InstalledClientTests."
    "test_claude_connects_when_enabled_and_blocks_project_entry_when_disabled": {
        "Claude Code is not installed"
    },
    "test_codex_auth_startup.CodexAuthStartupTests."
    "test_installed_codex_caches_and_refreshes_provider_placeholder": {
        "Codex is not installed"
    },
    "test_skills.SkillTests."
    "test_installed_claude_discovers_skill_through_directory_symlink": {
        "Claude Code is not installed"
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="unittest discovery start directory")
    parser.add_argument(
        "--allow-missing-clients",
        action="store_true",
        help="allow only the five installed-agent tests to skip for missing clients",
    )
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(args.directory)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    allowed = MISSING_CLIENT_SKIPS if args.allow_missing_clients else {}
    unexpected = [
        (test.id(), reason)
        for test, reason in result.skipped
        if reason not in allowed.get(test.id(), set())
    ]
    for test_id, reason in unexpected:
        print(f"Unexpected skip: {test_id}: {reason}", file=sys.stderr)
    if result.testsRun == 0:
        print("No tests discovered", file=sys.stderr)
    return int(not result.wasSuccessful() or bool(unexpected) or result.testsRun == 0)


if __name__ == "__main__":
    raise SystemExit(main())
