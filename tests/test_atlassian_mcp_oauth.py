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
    def run_sync(self, *, second_page_fails: bool = False) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            commands = root / "bin"
            commands.mkdir()
            log = root / "openshell.log"
            state = root / "openshell" / "atlassian-mcp-oauth.json"
            state.parent.mkdir()
            state.write_text(json.dumps({"providers": {"atlassian-mcp": {
                "client_id": "test-client", "refresh_token": "test-refresh",
            }}}))

            openshell = commands / "openshell"
            openshell.write_text("""#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$OPEN_SHELL_TEST_LOG"
case "$*" in
  'provider list -o json')
    printf '%s\\n' '{"providers":[],"next_page_token":"next"}' ;;
  'provider list -o json --page-token next')
    if [[ "$FAIL_SECOND_PAGE" == 1 ]]; then exit 1; fi
    printf '%s\\n' '{"providers":[{"name":"atlassian-mcp"}],"next_page_token":""}' ;;
  'provider update atlassian-mcp --from-existing') exit 0 ;;
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
            })
            result = subprocess.run(["bash", str(SCRIPT), "sync"], env=env,
                                    capture_output=True, text=True, check=False)
            return result, log.read_text().splitlines()

    def test_existing_provider_on_later_page_is_updated(self) -> None:
        result, commands = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, [
            "provider list -o json",
            "provider list -o json --page-token next",
            "provider update atlassian-mcp --from-existing",
        ])

    def test_page_failure_does_not_attempt_create(self) -> None:
        result, commands = self.run_sync(second_page_fails=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to list OpenShell providers", result.stderr)
        self.assertEqual(commands, [
            "provider list -o json",
            "provider list -o json --page-token next",
        ])


if __name__ == "__main__":
    unittest.main()
