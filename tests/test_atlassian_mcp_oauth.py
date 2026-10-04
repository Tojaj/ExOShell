from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "atlassian-mcp-oauth.sh"


@unittest.skipUnless(shutil.which("jq") and shutil.which("openssl"), "requires jq and openssl")
class ProviderLookupTests(unittest.TestCase):
    def run_sync(self, *, provider: str = "exoshell-atlassian-mcp",
                 explicit_provider: bool = False, legacy_state: bool = False,
                 second_page_fails: bool = False, first_page_fails: bool = False,
                 malformed_listing: bool = False
                 ) -> tuple[subprocess.CompletedProcess[str], list[str], dict]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commands = root / "bin"
            commands.mkdir()
            log = root / "openshell.log"
            state = root / "openshell" / "atlassian-mcp-oauth.json"
            state.parent.mkdir()
            credentials = {"client_id": "test-client", "refresh_token": "test-refresh"}
            initial_state = credentials if legacy_state else {"providers": {provider: credentials}}
            if not legacy_state and provider != "atlassian-mcp":
                initial_state["providers"]["atlassian-mcp"] = {
                    "client_id": "old-client", "refresh_token": "old-refresh",
                }
            state.write_text(json.dumps(initial_state))

            openshell = commands / "openshell"
            openshell.write_text("""#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPEN_SHELL_TEST_LOG"
case "$*" in
  'provider list -o json')
    if [[ "$FAIL_FIRST_PAGE" == 1 ]]; then exit 1; fi
    if [[ "$MALFORMED_LISTING" == 1 ]]; then printf '{}'; exit 0; fi
    printf '%s\\n' '{"providers":[],"next_page_token":"next"}' ;;
  'provider list -o json --page-token next')
    if [[ "$FAIL_SECOND_PAGE" == 1 ]]; then exit 1; fi
    printf '{"providers":[{"name":"%s"}],"next_page_token":""}\\n' "$TEST_PROVIDER" ;;
  "provider update $TEST_PROVIDER --from-existing") exit 0 ;;
  *) exit 2 ;;
esac
""")
            openshell.chmod(0o755)

            curl = commands / "curl"
            curl.write_text("""#!/usr/bin/env bash
case "$*" in
  *oauth-protected-resource*)
    printf '%s\\n' '{"authorization_servers":["https://auth.example.com"]}' ;;
  *oauth-authorization-server*)
    printf '%s\\n' '{"authorization_endpoint":"https://auth.example.com/authorize","token_endpoint":"https://auth.example.com/token"}' ;;
  *'https://auth.example.com/token'*)
    printf '%s\\n' '{"access_token":"test-access","refresh_token":"test-rotated"}' ;;
  *) exit 2 ;;
esac
""")
            curl.chmod(0o755)

            env = os.environ.copy()
            env.update({
                "PATH": f"{commands}:{env['PATH']}",
                "XDG_CONFIG_HOME": str(root),
                "OPEN_SHELL_TEST_LOG": str(log),
                "FAIL_SECOND_PAGE": "1" if second_page_fails else "0",
                "FAIL_FIRST_PAGE": "1" if first_page_fails else "0",
                "MALFORMED_LISTING": "1" if malformed_listing else "0",
                "TEST_PROVIDER": provider,
            })
            arguments = ["bash", str(SCRIPT), "sync"]
            if explicit_provider:
                arguments += ["--provider", provider]
            result = subprocess.run(arguments, env=env,
                                    capture_output=True, text=True, check=False)
            return result, log.read_text().splitlines(), json.loads(state.read_text())

    def test_existing_provider_on_later_page_is_updated(self) -> None:
        result, commands, state = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, [
            "provider list -o json",
            "provider list -o json --page-token next",
            "provider update exoshell-atlassian-mcp --from-existing",
        ])

    def test_page_failure_does_not_attempt_create(self) -> None:
        result, commands, state = self.run_sync(second_page_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to list OpenShell providers", result.stderr)
        self.assertEqual(commands, [
            "provider list -o json",
            "provider list -o json --page-token next",
        ])

    def test_explicit_names_and_legacy_state(self) -> None:
        for provider, legacy in [("atlassian-mcp", False), ("custom-atlassian", False),
                                 ("atlassian-mcp", True)]:
            with self.subTest(provider=provider, legacy=legacy):
                result, commands, state = self.run_sync(
                    provider=provider, explicit_provider=True, legacy_state=legacy)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(commands[-1], f"provider update {provider} --from-existing")
                self.assertEqual(state["providers"][provider]["refresh_token"], "test-rotated")
                self.assertNotIn("exoshell-atlassian-mcp", state["providers"])

    def test_default_preserves_existing_state_key(self) -> None:
        result, commands, state = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state["providers"]["atlassian-mcp"]["refresh_token"], "old-refresh")
        self.assertEqual(state["providers"]["exoshell-atlassian-mcp"]["refresh_token"], "test-rotated")

    def test_first_page_failure_and_malformed_listing_do_not_create(self) -> None:
        for options in [{"first_page_fails": True}, {"malformed_listing": True}]:
            with self.subTest(options=options):
                result, commands, state = self.run_sync(**options)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(commands, ["provider list -o json"])

    def test_unkeyed_state_stays_under_old_name_with_new_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "openshell" / "atlassian-mcp-oauth.json"
            state.parent.mkdir()
            credentials = {"client_id": "old-client", "refresh_token": "old-refresh"}
            state.write_text(json.dumps(credentials))
            env = dict(os.environ, XDG_CONFIG_HOME=temporary)
            result = subprocess.run(["bash", str(SCRIPT), "status"], env=env,
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no state found for provider 'exoshell-atlassian-mcp'", result.stderr)
            self.assertEqual(json.loads(state.read_text()), {"providers": {"atlassian-mcp": credentials}})
            result = subprocess.run(["bash", str(SCRIPT), "status", "--provider", "atlassian-mcp"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_create_uses_namespaced_type_and_selected_instance(self) -> None:
        # Exercise the storage boundary with a fake authorization result; the
        # browser authorization flow is unrelated to profile naming.
        functions = SCRIPT.read_text().split("# --- main ---")[0]
        for provider in ["exoshell-atlassian-mcp", "atlassian-mcp", "custom-atlassian"]:
            with self.subTest(provider=provider):
                shell = functions + '''
openshell() {
  [[ "$ATLASSIAN_MCP_BEARER_TOKEN" == "test-access" ]] || return 3
  printf '%s\\n' "$*"
}
PROVIDER_NAME="$TEST_PROVIDER"
store_access_token create test-access
'''
                result = subprocess.run(["bash", "-c", shell],
                                        env=dict(os.environ, TEST_PROVIDER=provider),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(),
                                 f"provider create --name {provider} --type exoshell-atlassian-mcp --from-existing")


if __name__ == "__main__":
    unittest.main()
