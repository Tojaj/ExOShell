from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import exoshell_agent as launcher

STARTUP = runpy.run_path(str(ROOT / "sandboxes/exoshell-base/exoshell-agent"))


class ModelDefaultsTests(unittest.TestCase):
    def test_config_selection_overrides_and_clearing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "config.toml"
            path.write_text(
                '[agents.codex]\nmodel = "example-model"\neffort = "high"\n'
                '[agents.claude]\nmodel = "sonnet"\neffort = "medium"\n'
                '[agents.opencode]\nmodel = "example/model"\neffort = "custom"\n'
            )
            config = launcher.load_config(path, required=True)
            for agent, model, effort in (
                ("codex", "example-model", "high"), ("claude", "sonnet", "medium"),
                ("opencode", "example/model", "custom"),
            ):
                for extra, wanted in (
                    ([], (model, effort)), (["--model", "other"], ("other", effort)),
                    (["--effort", "low"], (model, "low")),
                    (["--no-model"], (None, effort)), (["--no-effort"], (model, None)),
                    (["--no-model", "--no-effort"], (None, None)),
                ):
                    with self.subTest(agent=agent, extra=extra):
                        args = launcher.parser().parse_args(["--agent", agent, "--no-policy", *extra])
                        settings = launcher.resolve_settings(args, config, cwd=directory)
                        self.assertEqual((settings["model"], settings["effort"]), wanted)
            for content, wanted in (
                ("", (None, None)), ('[agents.codex]\nmodel = "example"\n', ("example", None)),
                ('[agents.codex]\neffort = "high"\n', (None, "high")),
            ):
                path.write_text(content)
                settings = launcher.resolve_settings(
                    launcher.parser().parse_args(["--no-policy"]),
                    launcher.load_config(path, required=True), cwd=directory,
                )
                self.assertEqual((settings["model"], settings["effort"]), wanted)

    def test_invalid_config_and_empty_cli_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "config.toml"
            for key in ("model", "effort"):
                for value in ('""', '"  "', "42", "true", "[]", "{}"):
                    path.write_text(f"[agents.claude]\n{key} = {value}\n")
                    with self.subTest(key=key, value=value), self.assertRaises(launcher.LauncherError):
                        launcher.load_config(path, required=True)
                path.write_text(f'{key} = "value"\n')
                with self.assertRaisesRegex(launcher.LauncherError, "unknown configuration"):
                    launcher.load_config(path, required=True)
                args = launcher.parser().parse_args(["--no-policy", f"--{key}", " "])
                with self.assertRaises(launcher.LauncherError):
                    launcher.resolve_settings(args, {}, cwd=directory)

    def command(self, agent: str, arguments: list[str], **defaults):
        return launcher.agent_command({"agent": agent, "model": "example/model", "effort": "high", **defaults}, arguments)

    def test_codex_quotes_toml_and_preserves_native_overrides(self) -> None:
        model = 'model "quote" \\ newline\n$(touch nope)'
        arguments = ["exec", "-c", 'model_reasoning_effort="low"', "--", "literal --model"]
        command, _ = self.command("codex", arguments, model=model)
        self.assertEqual(tomllib.loads(command[2])["model"], model)
        self.assertEqual(tomllib.loads(command[4])["model_reasoning_effort"], "high")
        self.assertEqual(command[5:], arguments)
        self.assertEqual(arguments[0], "exec")
        for override in (["--model", "native"], ["--model=native"], ["-mnative"], ["-m", "native"]):
            command, _ = self.command("codex", override)
            self.assertEqual(command, ["codex", "--config", 'model_reasoning_effort="high"', *override])
        command, _ = self.command("codex", ["--", "--model", "prompt"])
        self.assertEqual(command[-3:], ["--", "--model", "prompt"])
        self.assertIn('model="example/model"', command)

    def test_claude_native_overrides_avoid_duplicate_options(self) -> None:
        for arguments in (["--model", "native", "--effort", "low"],
                          ["--model=native", "--effort=low"]):
            command, _ = self.command("claude", arguments)
            self.assertEqual(command, ["claude", *arguments])
        command, _ = self.command("claude", ["--effort", "low", "prompt"])
        self.assertEqual(command, ["claude", "--model", "example/model", "--effort", "low", "prompt"])

    def test_opencode_tui_pair_and_native_model(self) -> None:
        for arguments, wanted in (([], "example/model"), (["-m", "native/model"], "native/model"),
                                  (["--model=native/model"], "native/model")):
            command, settings = self.command("opencode", arguments)
            self.assertEqual(settings["opencode_defaults"], {"model": wanted, "variant": "high"})
            if arguments:
                self.assertEqual(command[-len(arguments):], arguments)
        with self.assertRaisesRegex(launcher.LauncherError, "requires an explicit model"):
            self.command("opencode", [], model=None)
        command, settings = self.command("opencode", [], effort=None)
        self.assertEqual(command, ["opencode", "--model", "example/model"])
        self.assertNotIn("opencode_defaults", settings)

    def test_opencode_run_variant_follows_subcommand(self) -> None:
        arguments = ["run", "--model", "native/model", "prompt"]
        command, settings = self.command("opencode", arguments)
        self.assertEqual(command, ["opencode", "run", "--variant", "high", *arguments[1:]])
        self.assertNotIn("opencode_defaults", settings)
        arguments = ["run", "--variant=custom", "prompt"]
        command, _ = self.command("opencode", arguments)
        self.assertEqual(command, ["opencode", "--model", "example/model", *arguments])
        arguments = ["--model", "native/model", "--pure", "run", "prompt"]
        command, settings = self.command("opencode", arguments)
        self.assertEqual(command, ["opencode", *arguments[:4], "--variant", "high", "prompt"])
        self.assertNotIn("opencode_defaults", settings)
        command, settings = self.command("opencode", ["--prompt", "run"])
        self.assertIn("opencode_defaults", settings)

    def test_opencode_error_precedes_external_commands_and_verbose_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "config.toml"
            path.write_text('[agents.opencode]\nmodel = "example/model"\neffort = "high"\n')
            with mock.patch.object(launcher.subprocess, "run") as run:
                with self.assertRaisesRegex(launcher.LauncherError, "requires an explicit model"):
                    launcher.run(["--config", str(path), "--agent", "opencode", "--no-model", "--no-policy"], cwd=directory)
                run.assert_not_called()
            with mock.patch.object(launcher.subprocess, "run", return_value=mock.Mock(returncode=0)), \
                    mock.patch.object(launcher, "git_identity", return_value=("Example", "user@example.com")), \
                    mock.patch.object(launcher, "_verbose_value") as report:
                launcher.run(["--config", str(path), "--agent", "opencode", "--no-policy", "-v"], cwd=directory)
                report.assert_any_call("model", "example/model")
                report.assert_any_call("effort", "high")
            command, settings = self.command("opencode", [])
            env_args = launcher.environment_args({**launcher.DEFAULTS, **settings}, "Example", "user@example.com")
            payload = next(value for value in env_args if value.startswith("EXOSHELL_OPENCODE_DEFAULTS="))
            self.assertEqual(json.loads(payload.split("=", 1)[1]), {"model": "example/model", "variant": "high"})


class OpenCodeDefaultsStartupTests(unittest.TestCase):
    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_launcher_pair_reaches_helper_and_preserves_forwarded_arguments(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            directory = Path(temporary)
            executable = directory / "opencode"
            executable.write_text(
                '#!/usr/bin/env python3\n'
                'import json,os,sys\n'
                'print(json.dumps([sys.argv[1:],json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])]))\n'
            )
            executable.chmod(0o755)
            settings = {**launcher.DEFAULTS, "agent": "opencode", "model": "example/model",
                        "effort": "high", "project": directory, "host_share": directory,
                        "container_project": temporary}
            arguments = ["--prompt", "prompt with spaces and $(literal)"]
            command = launcher.create_command(settings, arguments, "Example", "user@example.com")
            environment = {"PATH": temporary + os.pathsep + os.environ["PATH"], "HOME": temporary}
            for index, argument in enumerate(command):
                if argument == "--env":
                    key, value = command[index + 1].split("=", 1)
                    environment[key] = value
            environment["OPENCODE_CONFIG_CONTENT"] = '{"agent":{"custom":{"variant":"low"}}}'
            separator = command.index("--")
            result = subprocess.run(
                [str(ROOT / "sandboxes/exoshell-base/exoshell-agent"), *command[separator + 2:]],
                env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            forwarded, config = json.loads(result.stdout)
            self.assertEqual(forwarded, ["--model", "example/model", *arguments])
            self.assertEqual(config["agent"]["plan"], {"model": "example/model", "variant": "high"})
            self.assertEqual(config["agent"]["custom"], {"variant": "low"})
            self.assertFalse(config["mcp"]["atlassian"]["enabled"])

    def test_inline_merge_preserves_custom_agents_permissions_and_mcp(self) -> None:
        original = {
            "instructions": ["/etc/example.md"], "agent": {
                "build": {"permission": {"edit": "ask"}, "variant": "low"},
                "custom": {"model": "other/model", "variant": "custom"},
            }, "mcp": {"atlassian": {"timeout": 123}, "other": {"enabled": True}},
        }
        environment = {"OPENCODE_CONFIG_CONTENT": json.dumps(original),
                       "EXOSHELL_OPENCODE_DEFAULTS": json.dumps({"model": "example/model", "variant": "high"})}
        STARTUP["initialize_opencode_defaults"](["opencode"], environment)
        STARTUP["initialize_atlassian_mcp"](["opencode"], environment, Path("/workspace"))
        merged = json.loads(environment["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(merged["instructions"], original["instructions"])
        self.assertEqual(merged["agent"]["custom"], original["agent"]["custom"])
        self.assertEqual(merged["agent"]["build"], {"permission": {"edit": "ask"}, "model": "example/model", "variant": "high"})
        self.assertEqual(merged["agent"]["plan"], {"model": "example/model", "variant": "high"})
        self.assertEqual(merged["mcp"], {"atlassian": {"timeout": 123, "enabled": False}, "other": {"enabled": True}})
        self.assertNotIn("EXOSHELL_OPENCODE_DEFAULTS", environment)

    def test_missing_defaults_and_other_agents_leave_config_alone(self) -> None:
        for command, payload in ((["opencode"], None), (["codex"], "ignored")):
            environment = {"OPENCODE_CONFIG_CONTENT": "existing"}
            if payload is not None:
                environment["EXOSHELL_OPENCODE_DEFAULTS"] = payload
            STARTUP["initialize_opencode_defaults"](command, environment)
            self.assertEqual(environment["OPENCODE_CONFIG_CONTENT"], "existing")

    def test_invalid_defaults_and_inline_config_fail_cleanly(self) -> None:
        pair = json.dumps({"model": "example/model", "variant": "high"})
        for payload, content in (("invalid", "{}"), ("[]", "{}"), ("{}", "{}"),
                                 (pair, "[]"), (pair, '{"agent": []}'),
                                 (pair, '{"agent": {"build": []}}')):
            with self.subTest(payload=payload, content=content), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as error:
                    STARTUP["initialize_opencode_defaults"](["opencode"], {
                        "EXOSHELL_OPENCODE_DEFAULTS": payload, "OPENCODE_CONFIG_CONTENT": content,
                    })
                self.assertEqual(error.exception.code, 2)
