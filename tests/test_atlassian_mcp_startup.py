from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import threading
import tomllib
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "sandboxes/exoshell-base"
STARTUP = runpy.run_path(str(IMAGE / "exoshell-agent"))
INITIALIZE = STARTUP["initialize_atlassian_mcp"]
CLAUDE = STARTUP["initialize_claude_mcp"]
KEY = STARTUP["ATLASSIAN_KEY"]


class AtlassianStartupTests(unittest.TestCase):
    def test_codex_state_wins_after_existing_overrides_before_delimiter(self) -> None:
        command = ["/usr/bin/codex", "exec", "--config",
                   "mcp_servers.atlassian.enabled=true", "--", "prompt with spaces", "$(syntax)"]
        for credential, expected in ((None, "false"), ("", "false"), ("opaque", "true")):
            with self.subTest(credential=credential):
                environment = {} if credential is None else {KEY: credential}
                original = command.copy()
                result = INITIALIZE(command, environment, Path("/workspace/project"))
                self.assertEqual(result, command[:4] +
                                 ["--config", f"mcp_servers.atlassian.enabled={expected}"] + command[4:])
                self.assertEqual(command, original)
                self.assertNotIn("opaque", result)
        self.assertEqual(INITIALIZE(["codex"], {}, Path("/workspace")),
                         ["codex", "--config", "mcp_servers.atlassian.enabled=false"])

    def test_opencode_merges_only_atlassian_state_without_disclosing_credential(self) -> None:
        original = {
            "model": "example/model",
            "mcp": {"other": {"type": "remote", "url": "https://example.com/mcp"},
                    "atlassian": {"enabled": True, "timeout": 12345}},
        }
        command = ["/usr/local/bin/opencode", "run", "prompt with spaces"]
        for credential, expected in ((None, False), ("", False), ("opaque", True)):
            with self.subTest(credential=credential):
                environment = {"OPENCODE_CONFIG_CONTENT": json.dumps(original),
                               "OPENCODE_CONFIG": "/etc/example.json"}
                if credential is not None:
                    environment[KEY] = credential
                self.assertEqual(INITIALIZE(command, environment, Path("/workspace")), command)
                wanted = copy.deepcopy(original)
                wanted["mcp"]["atlassian"]["enabled"] = expected
                self.assertEqual(json.loads(environment["OPENCODE_CONFIG_CONTENT"]), wanted)
                self.assertEqual(environment["OPENCODE_CONFIG"], "/etc/example.json")
                self.assertNotIn("opaque", environment["OPENCODE_CONFIG_CONTENT"])

    def test_opencode_empty_config_and_repeated_transitions(self) -> None:
        environment = {}
        for credential, expected in ((None, False), ("opaque", True), (None, False)):
            environment.pop(KEY, None)
            if credential is not None:
                environment[KEY] = credential
            INITIALIZE(["opencode"], environment, Path("/workspace"))
            self.assertEqual(json.loads(environment["OPENCODE_CONFIG_CONTENT"]),
                             {"mcp": {"atlassian": {"enabled": expected}}})

    def test_opencode_invalid_config_fails_without_overwriting_or_disclosure(self) -> None:
        for value in ('{"sensitive-value":', '[]', '{"mcp":null}', '{"mcp":{"atlassian":[]}}'):
            with self.subTest(value=value), mock.patch("sys.stderr") as stderr:
                environment = {"OPENCODE_CONFIG_CONTENT": value}
                with self.assertRaises(SystemExit) as error:
                    INITIALIZE(["opencode"], environment, Path("/workspace"))
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(environment["OPENCODE_CONFIG_CONTENT"], value)
                self.assertNotIn("sensitive-value", str(stderr.write.call_args_list))

    def test_unrecognized_commands_are_untouched(self) -> None:
        command = ["python3", "-c", "code", "--"]
        environment = {KEY: "opaque", "OPENCODE_CONFIG_CONTENT": "invalid"}
        original = environment.copy()
        self.assertEqual(INITIALIZE(command, environment, Path("/workspace")), command)
        self.assertEqual(environment, original)

    def test_claude_dispatch_uses_credential_presence(self) -> None:
        with mock.patch.dict(INITIALIZE.__globals__, initialize_claude_mcp=mock.Mock()) as namespace:
            initialize = namespace["initialize_claude_mcp"]
            for credential, expected in ((None, False), ("", False), ("opaque", True)):
                environment = {} if credential is None else {KEY: credential}
                command = ["/usr/local/bin/claude", "--print", "prompt"]
                self.assertEqual(INITIALIZE(command, environment, Path("/workspace")), command)
                initialize.assert_called_with(environment, Path("/workspace"), expected)

    def test_image_defaults_and_template_have_no_active_claude_server(self) -> None:
        codex = tomllib.loads((IMAGE / "codex.config.toml").read_text())
        opencode = json.loads((IMAGE / "opencode.json").read_text())
        self.assertFalse(codex["mcp_servers"]["atlassian"]["enabled"])
        self.assertFalse(opencode["mcp"]["atlassian"]["enabled"])
        dockerfile = (IMAGE / "Dockerfile").read_text()
        self.assertIn("ENV CLAUDE_CONFIG_DIR=/sandbox/.claude", dockerfile)
        self.assertIn("claude.config.json /etc/exoshell/claude-atlassian.json", dockerfile)
        self.assertNotIn("claude.config.json /sandbox/.claude.json", dockerfile)

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_helper_executes_with_prepared_argv_environment_and_project(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            directory = Path(temporary)
            executable = directory / "opencode"
            executable.write_text(
                '#!/usr/bin/env python3\nimport json,os,sys\n'
                'print(json.dumps([os.getcwd(),sys.argv[1:],'
                'json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])]))\n'
                'sys.exit(17)\n'
            )
            executable.chmod(0o755)
            environment = os.environ.copy()
            environment.pop(KEY, None)
            environment.pop("EXOSHELL_GWS", None)
            environment.pop("OPENCODE_CONFIG_CONTENT", None)
            result = subprocess.run([str(IMAGE / "exoshell-agent"), temporary, "--", str(executable),
                                     "prompt with spaces", "$(syntax)"], env=environment,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 17, result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             [temporary, ["prompt with spaces", "$(syntax)"],
                              {"mcp": {"atlassian": {"enabled": False}}}])


class ClaudeMcpStateTests(unittest.TestCase):
    def test_enable_disable_transitions_preserve_unrelated_state(self) -> None:
        project = Path("/workspace/project")
        other_server = {"type": "http", "url": "https://example.com/mcp"}
        original = {
            "theme": "dark",
            "mcpServers": {"other": other_server, "atlassian": {"url": "old"}},
            "projects": {
                str(project): {"hasTrustDialogAccepted": True,
                               "mcpServers": {"local": other_server, "atlassian": {"url": "old-local"}},
                               "disabledMcpServers": ["other", "atlassian", "atlassian"]},
                "/workspace/other": {"disabledMcpServers": ["atlassian"]},
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / ".claude.json"
            target.write_text(json.dumps(original))
            environment = {"CLAUDE_CONFIG_DIR": temporary, KEY: "opaque"}
            definition = json.loads((IMAGE / "claude.config.json").read_text())["mcpServers"]["atlassian"]
            for enabled in (True, False, True, False):
                CLAUDE(environment, project, enabled, IMAGE / "claude.config.json")
                config = json.loads(target.read_text())
                state = config["projects"][str(project)]
                self.assertEqual(config["theme"], "dark")
                self.assertEqual(config["mcpServers"]["other"], other_server)
                self.assertEqual(state["mcpServers"]["local"], other_server)
                self.assertTrue(state["hasTrustDialogAccepted"])
                self.assertEqual(config["projects"]["/workspace/other"], original["projects"]["/workspace/other"])
                if enabled:
                    self.assertEqual(config["mcpServers"]["atlassian"], definition)
                    self.assertEqual(state["mcpServers"]["atlassian"], definition)
                    self.assertEqual(state["disabledMcpServers"], ["other"])
                else:
                    self.assertNotIn("atlassian", config["mcpServers"])
                    self.assertNotIn("atlassian", state["mcpServers"])
                    self.assertEqual(state["disabledMcpServers"], ["other", "atlassian"])
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                self.assertNotIn("opaque", target.read_text())
                self.assertEqual(list(directory.iterdir()), [target])

    def test_missing_config_uses_home_agent_directory_and_does_not_need_template_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment = {"HOME": temporary}
            CLAUDE(environment, Path("/workspace"), False, Path("/missing-template"))
            target = Path(temporary) / ".claude" / ".claude.json"
            self.assertEqual(environment["CLAUDE_CONFIG_DIR"], str(target.parent))
            config = json.loads(target.read_text())
            self.assertEqual(config["mcpServers"], {})
            self.assertEqual(config["projects"]["/workspace"]["disabledMcpServers"], ["atlassian"])

    def test_invalid_state_is_preserved_and_error_does_not_disclose_values(self) -> None:
        for value in ('{"sensitive-value":', '[]', '{"mcpServers":null}',
                      '{"projects":[]}', '{"projects":{"/workspace":{"disabledMcpServers":{}}}}'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / ".claude.json"
                target.write_text(value)
                with mock.patch("sys.stderr") as stderr, self.assertRaises(SystemExit):
                    CLAUDE({"CLAUDE_CONFIG_DIR": temporary}, Path("/workspace"), False)
                self.assertEqual(target.read_text(), value)
                self.assertNotIn("sensitive-value", str(stderr.write.call_args_list))

    def test_failed_rename_keeps_original_without_partial_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / ".claude.json"
            target.write_text('{"theme":"dark"}')
            with mock.patch("os.replace", side_effect=OSError("sensitive-value")), \
                 mock.patch("sys.stderr") as stderr, self.assertRaises(SystemExit):
                CLAUDE({"CLAUDE_CONFIG_DIR": temporary}, Path("/workspace"), False)
            self.assertEqual(target.read_text(), '{"theme":"dark"}')
            self.assertEqual(list(directory.iterdir()), [target])
            self.assertNotIn("sensitive-value", str(stderr.write.call_args_list))


class InstalledClientTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("codex"), "Codex is not installed")
    def test_codex_accepts_managed_override_after_conflicting_cli_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment = {**os.environ, "CODEX_HOME": temporary}
            for enabled in (False, True):
                environment.pop(KEY, None)
                if enabled:
                    environment[KEY] = "test-placeholder"
                command = INITIALIZE(["codex", "mcp", "list", "--json", "-c",
                                      f"mcp_servers.atlassian.enabled={str(not enabled).lower()}",
                                      "-c", 'mcp_servers.atlassian.url="https://example.com/mcp"'],
                                     environment, Path(temporary))
                result = subprocess.run(command, env=environment, cwd=temporary,
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, "Codex could not load runtime configuration")
                server = next(server for server in json.loads(result.stdout) if server["name"] == "atlassian")
                self.assertEqual(server["enabled"], enabled)

    @unittest.skipUnless(shutil.which("opencode"), "OpenCode is not installed")
    def test_opencode_runtime_override_wins_over_image_and_inline_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            environment = {**os.environ, "OPENCODE_CONFIG": str(IMAGE / "opencode.json")}
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
                environment[key] = str(directory / key)
            for enabled in (False, True):
                environment.pop(KEY, None)
                if enabled:
                    environment[KEY] = "test-placeholder"
                environment["OPENCODE_CONFIG_CONTENT"] = json.dumps({
                    "autoupdate": False, "mcp": {"atlassian": {"enabled": not enabled}},
                })
                command = INITIALIZE(["opencode", "debug", "config"], environment, directory)
                result = subprocess.run(command, env=environment, cwd=directory,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, "OpenCode could not load runtime configuration")
                config = json.loads(result.stdout)
                self.assertEqual(config["mcp"]["atlassian"]["enabled"], enabled)
                self.assertFalse(config["mcp"]["atlassian"]["oauth"])
                self.assertFalse(config["autoupdate"])

    @unittest.skipUnless(shutil.which("claude"), "Claude Code is not installed")
    def test_claude_connects_when_enabled_and_blocks_project_entry_when_disabled(self) -> None:
        requests = []

        class McpHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(request["method"])
                if "id" not in request:
                    self.send_response(202)
                    self.end_headers()
                    return
                result = {}
                if request["method"] == "initialize":
                    result = {"protocolVersion": request["params"]["protocolVersion"],
                              "capabilities": {}, "serverInfo": {"name": "test", "version": "1"}}
                response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
                data = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), McpHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                environment = {**os.environ, "CLAUDE_CONFIG_DIR": str(directory / "claude"),
                               KEY: "test-placeholder"}
                definition = {"mcpServers": {"atlassian": {
                    "type": "http", "url": f"http://127.0.0.1:{server.server_port}/mcp",
                    "headers": {"Authorization": "Bearer ${ATLASSIAN_MCP_BEARER_TOKEN}"},
                }}}
                template = directory / "template.json"
                template.write_text(json.dumps(definition))
                CLAUDE(environment, directory, True, template)
                result = subprocess.run(["claude", "mcp", "get", "atlassian"], env=environment,
                                        cwd=directory, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, "Claude could not load runtime configuration")
                self.assertIn("Connected", result.stdout)
                self.assertIn("initialize", requests)
                requests.clear()

                # A project entry survives removing the generated user/local
                # entry, but the per-project disabled list must stop connection.
                (directory / ".mcp.json").write_text(json.dumps(definition))
                (directory / "claude/settings.json").write_text('{"enableAllProjectMcpServers":true}')
                environment.pop(KEY)
                CLAUDE(environment, directory, False, template)
                result = subprocess.run(["claude", "mcp", "get", "atlassian"], env=environment,
                                        cwd=directory, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, "Claude could not load project configuration")
                self.assertIn("Disabled for this project", result.stdout)
                self.assertEqual(requests, [])

                (directory / ".mcp.json").unlink()
                result = subprocess.run(["claude", "mcp", "get", "atlassian"], env=environment,
                                        cwd=directory, capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('No MCP server named "atlassian"', result.stderr)
                self.assertEqual(requests, [])
        finally:
            server.shutdown()
            worker.join(timeout=2)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
