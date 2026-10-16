from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "sandboxes/exoshell-base/exoshell-agent"
STARTUP = runpy.run_path(str(HELPER))
INITIALIZE = STARTUP["initialize_opencode_websearch"]
KEY = "TAVILY_API_KEY"


class TavilyStartupTests(unittest.TestCase):
    def test_selects_tavily_without_serializing_credential(self) -> None:
        for content in (None, "", "{}"):
            with self.subTest(content=content):
                environment = {KEY: "test-credential"}
                if content is not None:
                    environment["OPENCODE_CONFIG_CONTENT"] = content
                INITIALIZE(["/usr/local/bin/opencode", "run", "prompt"], environment)
                self.assertEqual(json.loads(environment["OPENCODE_CONFIG_CONTENT"]),
                                 {"websearch": {"provider": "tavily"}})
                self.assertNotIn("test-credential", environment["OPENCODE_CONFIG_CONTENT"])
                self.assertEqual(environment[KEY], "test-credential")

    def test_skips_missing_or_empty_key_and_other_commands(self) -> None:
        for command, credential in ((["opencode"], None), (["opencode"], ""),
                                    (["codex"], "test-credential"),
                                    (["claude"], "test-credential")):
            with self.subTest(command=command, credential=credential):
                environment = {"OPENCODE_CONFIG_CONTENT": "not parsed"}
                if credential is not None:
                    environment[KEY] = credential
                original = environment.copy()
                INITIALIZE(command, environment)
                self.assertEqual(environment, original)

    def test_preserves_explicit_inline_selection_and_disabled_search(self) -> None:
        for search in (False, {"provider": "exa"}, {"provider": "random"},
                       {"provider": "tavily"}, {}):
            with self.subTest(search=search):
                original = {"websearch": search, "model": "example/model",
                            "mcp": {"servers": {"other": {"type": "local", "command": ["example"]}}}}
                environment = {KEY: "test-credential", "OPENCODE_CONFIG": "/not-read.jsonc",
                               "OPENCODE_CONFIG_CONTENT": json.dumps(original)}
                INITIALIZE(["opencode"], environment)
                expected = copy.deepcopy(original)
                if isinstance(search, dict):
                    expected["websearch"].setdefault("provider", "tavily")
                self.assertEqual(json.loads(environment["OPENCODE_CONFIG_CONTENT"]), expected)
                self.assertEqual(environment["OPENCODE_CONFIG"], "/not-read.jsonc")

    def test_invalid_config_fails_without_overwrite_or_disclosure(self) -> None:
        for content in ('{"sensitive-value":', '[]', '{"websearch":null}',
                        '{"websearch":true}', '{"websearch":"sensitive-value"}'):
            with self.subTest(content=content), mock.patch("sys.stderr") as stderr:
                environment = {KEY: "test-credential", "OPENCODE_CONFIG_CONTENT": content}
                original = environment.copy()
                with self.assertRaises(SystemExit) as error:
                    INITIALIZE(["opencode"], environment)
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(environment, original)
                self.assertNotIn("sensitive-value", str(stderr.write.call_args_list))
                self.assertNotIn("test-credential", str(stderr.write.call_args_list))

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_helper_combines_search_model_and_mcp_without_writing_project_config(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            directory = Path(temporary)
            executable = directory / "opencode"
            executable.write_text(
                '#!/usr/bin/env python3\nimport json,os,sys\n'
                'print(json.dumps([os.getcwd(),sys.argv[1:],'
                'json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])]))\n'
            )
            executable.chmod(0o755)
            # Never inherit attached credentials or inspect live agent state.
            environment = {"PATH": os.defpath, "HOME": temporary, KEY: "test-credential",
                           "EXOSHELL_OPENCODE_DEFAULTS": json.dumps({"model": "example/model"})}
            result = subprocess.run([str(HELPER), temporary, "--", str(executable), "prompt"],
                                    env=environment, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            project, arguments, config = json.loads(result.stdout)
            self.assertEqual(project, temporary)
            self.assertEqual(arguments, ["prompt"])
            self.assertEqual(config["websearch"], {"provider": "tavily"})
            self.assertEqual(config["agents"], {"build": {"model": "example/model"},
                                              "plan": {"model": "example/model"}})
            self.assertTrue(config["mcp"]["servers"]["atlassian"]["disabled"])
            self.assertNotIn("test-credential", result.stdout + result.stderr)
            self.assertEqual(list(directory.iterdir()), [executable])


if __name__ == "__main__":
    unittest.main()
