from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "sandboxes/exoshell-base"
STARTUP = runpy.run_path(str(IMAGE / "exoshell-agent"))
INITIALIZE = STARTUP["initialize_codex_auth"]


def isolated_environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("CODEX_AUTH_") or key in (
            "OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN",
            "ATLASSIAN_MCP_BEARER_TOKEN", "GWS_CLIENT_ID", "GWS_CLIENT_SECRET",
            "GWS_REFRESH_TOKEN",
        ):
            environment.pop(key)
    environment["CODEX_HOME"] = str(home)
    return environment


class CodexAuthStartupTests(unittest.TestCase):
    def test_missing_key_and_other_commands_skip_login(self) -> None:
        with mock.patch.object(subprocess, "run") as run:
            for command, environment in (
                (["codex"], {}),
                (["/usr/bin/codex"], {"OPENAI_API_KEY": ""}),
                (["claude"], {"OPENAI_API_KEY": "opaque"}),
                (["opencode"], {"OPENAI_API_KEY": "opaque"}),
            ):
                INITIALIZE(command, environment, Path("/workspace"))
            run.assert_not_called()

    def test_login_failures_do_not_disclose_diagnostics(self) -> None:
        for outcome in (
            subprocess.CompletedProcess([], 1, b"sensitive-key", b"sensitive-key"),
            OSError("sensitive-key"),
        ):
            with self.subTest(outcome=type(outcome).__name__), \
                    mock.patch.object(subprocess, "run") as run, \
                    mock.patch("sys.stderr") as stderr:
                if isinstance(outcome, Exception):
                    run.side_effect = outcome
                else:
                    run.return_value = outcome
                with self.assertRaises(SystemExit) as error:
                    INITIALIZE(["codex"], {"OPENAI_API_KEY": "sensitive-key"}, Path("/workspace"))
                self.assertEqual(error.exception.code, 2)
                self.assertNotIn("sensitive-key", str(stderr.write.call_args_list))

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_helper_logs_in_before_session_and_stops_after_failed_login(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            directory = Path(temporary)
            executable = directory / "codex"
            executable.write_text(
                '#!/usr/bin/env python3\n'
                'import json,os,pathlib,sys\n'
                'state=pathlib.Path(os.environ["CODEX_HOME"])/"probe.json"\n'
                'if sys.argv[1:]==["login","--with-api-key"]:\n'
                '    key=sys.stdin.read()\n'
                '    state.write_text(json.dumps([key,os.getcwd()]))\n'
                '    print("login diagnostic "+key)\n'
                '    print("login diagnostic "+key,file=sys.stderr)\n'
                '    sys.exit(int(os.environ.get("PROBE_LOGIN_EXIT","0")))\n'
                'print(json.dumps([json.loads(state.read_text()),sys.argv[1:],os.getcwd()]))\n'
                'sys.exit(17)\n'
            )
            executable.chmod(0o755)
            environment = isolated_environment(directory)
            arguments = ["exec", "--", "prompt with spaces", "$(literal)"]
            for use_path in (False, True):
                environment["PATH"] = str(directory) + os.pathsep + os.environ["PATH"]
                environment["OPENAI_API_KEY"] = "opaque-placeholder"
                selected = str(executable) if use_path else "codex"
                result = subprocess.run(
                    [str(IMAGE / "exoshell-agent"), temporary, "--", selected, *arguments],
                    env=environment, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 17, result.stderr)
                self.assertEqual(json.loads(result.stdout), [
                    ["opaque-placeholder", temporary],
                    ["exec", "--config", "mcp_servers.atlassian.enabled=false", *arguments[1:]],
                    temporary,
                ])
                self.assertEqual(result.stderr, "")
            environment["PROBE_LOGIN_EXIT"] = "1"
            result = subprocess.run(
                [str(IMAGE / "exoshell-agent"), temporary, "--", str(executable)],
                env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "exoshell-agent: could not initialize Codex API-key login\n")

    @unittest.skipUnless(shutil.which("codex"), "Codex is not installed")
    def test_installed_codex_caches_and_refreshes_provider_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            # Use the image storage default without modifying system configuration.
            config = tomllib.loads((IMAGE / "codex.config.toml").read_text())
            self.assertEqual(config["cli_auth_credentials_store"], "file")
            (home / "config.toml").write_text('cli_auth_credentials_store = "file"\n')
            environment = isolated_environment(home)
            for credential in (
                "openshell:resolve:env:v1_OPENAI_API_KEY",
                "openshell:resolve:env:v2_OPENAI_API_KEY",
            ):
                environment["OPENAI_API_KEY"] = credential
                INITIALIZE([shutil.which("codex")], environment, ROOT)
                target = home / "auth.json"
                state = json.loads(target.read_text())
                self.assertEqual(state["auth_mode"], "apikey")
                self.assertEqual(state["OPENAI_API_KEY"], credential)
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                status = subprocess.run(["codex", "login", "status"], env=environment,
                                        capture_output=True)
                self.assertEqual(status.returncode, 0)


if __name__ == "__main__":
    unittest.main()
