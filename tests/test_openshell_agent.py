from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import exoshell_agent as launcher  # noqa: E402
sys.path.insert(0, str(ROOT / "policy-overlays"))
import apply as policy_apply  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_absent_implicit_config_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "missing.toml"
            self.assertEqual(launcher.load_config(path, required=False), {})
            with self.assertRaisesRegex(launcher.LauncherError, "does not exist"):
                launcher.load_config(path, required=True)

    def test_accepts_common_and_per_agent_providers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.toml"
            path.write_text(
                'agent = "claude"\nproviders = ["github"]\ngithub_host = "github.example.com"\n'
                '[agents.codex]\nproviders = ["openai"]\n'
                '[agents.claude]\nproviders = ["claude-api"]\n'
            )
            config = launcher.load_config(path, required=True)
            self.assertEqual(config["agent"], "claude")
            self.assertEqual(config["github_host"], "github.example.com")
            self.assertEqual(config["agents"]["claude"]["providers"], ["claude-api"])

    def test_rejects_malformed_unknown_types_agents_and_duplicates(self) -> None:
        cases = {
            "malformed": "image = [",
            "unknown": "surprise = true\n",
            "removed-sandbox-name": 'sandbox_name = "fixed"\n',
            "type": "gws = 1\n",
            "agent": 'agent = "other"\n',
            "agent-type": "agent = []\n",
            "unknown-agent": "[agents.other]\nproviders = []\n",
            "unknown-agent-key": "[agents.codex]\nimage = \"bad\"\n",
            "duplicate": 'providers = ["one", "one"]\n',
            "agent-duplicate": '[agents.codex]\nproviders = ["one", "one"]\n',
        }
        with tempfile.TemporaryDirectory() as temporary:
            for name, content in cases.items():
                with self.subTest(name=name):
                    path = Path(temporary) / f"{name}.toml"
                    path.write_text(content)
                    with self.assertRaises(launcher.LauncherError):
                        launcher.load_config(path, required=True)

    def test_config_paths_are_relative_to_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "config.toml"
            path.write_text('host_share = "source"\npolicy = "policy.yaml"\n')
            config = launcher.load_config(path, required=True)
            self.assertEqual(config["host_share"], root / "source")
            self.assertEqual(config["policy"], root / "policy.yaml")


class ResolutionTests(unittest.TestCase):
    def parse(self, *arguments: str) -> argparse.Namespace:
        return launcher.parser().parse_args(arguments)

    def test_codex_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary).resolve()
            settings = launcher.resolve_settings(self.parse(), {}, cwd=cwd)
            self.assertEqual(settings["agent"], "codex")
            self.assertFalse(settings["keep"])
            self.assertEqual(settings["providers"], ["openai"])
            self.assertEqual(settings["container_project"], "/workspace")

    def test_agent_selection_provider_composition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            config = {
                "providers": ["common"],
                "agents": {
                    "codex": {"providers": ["codex-provider"]},
                    "claude": {"providers": ["claude-provider"]},
                },
            }
            settings = launcher.resolve_settings(self.parse("--agent", "claude"), config, cwd=cwd)
            self.assertEqual(settings["providers"], ["common", "claude-provider"])

    def test_config_agent_and_keep_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            settings = launcher.resolve_settings(
                self.parse("--keep"), {"agent": "opencode"}, cwd=cwd
            )
            self.assertEqual(settings["agent"], "opencode")
            self.assertTrue(settings["keep"])

    def test_provider_override_and_clearing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            config = {"providers": ["common"], "agents": {"codex": {"providers": ["agent"]}}}
            replaced = launcher.resolve_settings(
                self.parse("--provider", "first", "--provider", "second"), config, cwd=cwd
            )
            self.assertEqual(replaced["providers"], ["first", "second"])
            cleared = launcher.resolve_settings(self.parse("--no-providers"), config, cwd=cwd)
            self.assertEqual(cleared["providers"], [])

    def test_duplicate_across_common_and_agent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(launcher.LauncherError, "duplicate provider"):
                launcher.resolve_settings(
                    self.parse(),
                    {"providers": ["same"], "agents": {"codex": {"providers": ["same"]}}},
                    cwd=Path(temporary),
                )

    def test_invalid_agent_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            self.parse("--agent", "invalid")

    def test_github_host_cli_override_clearing_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            config = {"github_host": "config.github.example.com"}
            overridden = launcher.resolve_settings(
                self.parse("--github-host", "cli.github.example.com"), config, cwd=cwd
            )
            self.assertEqual(overridden["github_host"], "cli.github.example.com")
            cleared = launcher.resolve_settings(self.parse("--no-github-host"), config, cwd=cwd)
            self.assertIsNone(cleared["github_host"])
            with self.assertRaisesRegex(launcher.LauncherError, "invalid GitHub host"):
                launcher.resolve_settings(self.parse("--github-host", "bad host"), {}, cwd=cwd)

    def test_nested_symlink_and_spaces_translate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            share = root / "share with spaces"
            project = share / "nested" / "project with spaces"
            project.mkdir(parents=True)
            link = root / "linked-project"
            link.symlink_to(project, target_is_directory=True)
            settings = launcher.resolve_settings(
                self.parse("--host-share", str(share), str(link)), {}, cwd=root
            )
            self.assertEqual(settings["container_project"], "/workspace/nested/project with spaces")

    def test_outside_share_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            share, project = root / "share", root / "elsewhere"
            share.mkdir()
            project.mkdir()
            with self.assertRaisesRegex(launcher.LauncherError, "outside host share"):
                launcher.resolve_settings(
                    self.parse("--host-share", str(share), str(project)), {}, cwd=root
                )


class OverlayBasePolicyTests(unittest.TestCase):
    def test_sandbox_name_is_required(self) -> None:
        with mock.patch.object(sys, "argv", ["apply.py"]):
            with self.assertRaises(SystemExit) as error:
                policy_apply.main()
        self.assertEqual(error.exception.code, 2)

    def test_missing_local_config_uses_public_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "missing.toml"
            self.assertEqual(policy_apply.default_base_file(config_path), policy_apply.PUBLIC_BASE_FILE)

    def test_local_config_policy_is_resolved_relative_to_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / ".exoshell.local.toml"
            config_path.write_text('policy = "policies/local.yaml"\n')
            self.assertEqual(policy_apply.default_base_file(config_path), root / "policies/local.yaml")


class CommandTests(unittest.TestCase):
    def settings(self, root: Path, agent: str) -> dict[str, object]:
        project = root / "source" / "project"
        project.mkdir(parents=True)
        return {
            "agent": agent,
            "image": "registry.example/image:latest",
            "keep": False,
            "providers": [],
            "policy": None,
            "kubeconfig": None,
            "gws": False,
            "github_host": None,
            "gitlab_host": None,
            "project": project,
            "host_share": root / "source",
            "container_project": "/workspace/project",
        }

    def test_each_agent_uses_image_state_and_executable(self) -> None:
        expected = {
            "codex": "codex",
            "claude": "claude",
            "opencode": "opencode",
        }
        for agent, executable in expected.items():
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as temporary:
                settings = self.settings(Path(temporary), agent)
                mounts = launcher.mount_config(settings)["podman"]["mounts"]
                self.assertEqual([mount["target"] for mount in mounts], ["/workspace"])
                command = launcher.create_command(
                    settings, ["--model", "model with spaces", "$(touch nope)"], "A User", "a@example.com"
                )
                self.assertEqual(
                    command[-7:-4],
                    ["/usr/local/bin/exoshell-agent", "/workspace/project", "--"],
                )
                self.assertEqual(command[-4], executable)
                self.assertEqual(command[-3:], ["--model", "model with spaces", "$(touch nope)"])
                self.assertNotIn("/bin/bash", command)
                self.assertIn("--no-keep", command)
                self.assertNotIn("--name", command)
                labels = [command[index + 1] for index, value in enumerate(command) if value == "--label"]
                self.assertEqual(
                    labels,
                    ["managed-by=exoshell", "project=project", f"agent={agent}"],
                )

    def test_keep_omits_no_keep(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = self.settings(Path(temporary), "codex")
            settings["keep"] = True
            command = launcher.create_command(settings, [], "A User", "a@example.com")
            self.assertNotIn("--no-keep", command)

    def test_gws_credentials_remain_on_tmpfs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = self.settings(Path(temporary), "opencode")
            settings["gws"] = True
            mounts = launcher.mount_config(settings)["podman"]["mounts"]
            self.assertEqual(mounts[-1], {"type": "tmpfs", "target": "/tmp/gws", "mode": 0o777})
            environment = launcher.environment_args(settings, "A User", "a@example.com")
            self.assertIn("EXOSHELL_GWS=1", environment)
            self.assertNotIn("GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=/tmp/gws/credentials.json", environment)

    def test_github_and_gitlab_hosts_configure_cli_and_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = self.settings(Path(temporary), "codex")
            settings["github_host"] = "github.example.com"
            settings["gitlab_host"] = "gitlab.example.com"
            arguments = launcher.environment_args(settings, "A User", "a@example.com")
            environment = arguments[1::2]
            self.assertIn("GH_HOST=github.example.com", environment)
            self.assertIn("GITLAB_HOST=gitlab.example.com", environment)
            self.assertIn("GIT_CONFIG_COUNT=6", environment)
            self.assertIn(
                "GIT_CONFIG_KEY_2=credential.https://github.example.com.helper", environment
            )
            self.assertIn(
                "GIT_CONFIG_VALUE_2=!/usr/bin/gh auth git-credential", environment
            )
            self.assertIn("GIT_CONFIG_VALUE_3=git@github.example.com:", environment)
            self.assertIn("GIT_CONFIG_KEY_4=credential.https://gitlab.example.com.helper", environment)
            self.assertIn("GIT_CONFIG_VALUE_5=git@gitlab.example.com:", environment)

    def test_project_label_normalization_truncation_and_fallback(self) -> None:
        cases = {
            "My Project__v2": "my-project-v2",
            "A" * 80: "a" * 63,
            "---": "project",
        }
        for basename, expected in cases.items():
            with self.subTest(basename=basename):
                self.assertEqual(launcher.project_label(Path("/tmp") / basename), expected)


class LauncherIntegrationTests(unittest.TestCase):
    def executable(self, path: Path, body: str) -> None:
        path.write_text("#!/usr/bin/bash\nset -euo pipefail\n" + body)
        path.chmod(0o755)

    def fake_environment(self, root: Path) -> tuple[dict[str, str], Path, Path]:
        binaries = root / "bin"
        binaries.mkdir()
        capture = root / "openshell.args"
        self.executable(binaries / "podman", '[[ "$*" == "image exists localhost/test-image:latest" ]]\n')
        self.executable(
            binaries / "git",
            'case "${!#}" in user.name) printf "%s\\n" "Test User";; user.email) printf "%s\\n" "test@example.com";; *) exit 1;; esac\n',
        )
        self.executable(binaries / "openshell", 'printf "%s\\n" "$@" > "$CAPTURE"\n')
        environment = os.environ.copy()
        environment.update({"PATH": f"{binaries}:{environment['PATH']}", "CAPTURE": str(capture)})
        return environment, capture, binaries

    def test_generic_wrapper_with_fake_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "share with spaces" / "project"
            project.mkdir(parents=True)
            policy = root / "policies" / "local.yaml"
            policy.parent.mkdir()
            policy.write_text("network_policies: {}\n")
            config = root / "launcher.toml"
            config.write_text(
                textwrap.dedent(
                    f'''\
                    image = "localhost/test-image:latest"
                    policy = "policies/local.yaml"
                    gitlab_host = "gitlab.example.com"
                    host_share = "{project.parent}"
                    providers = ["common"]
                    [agents.opencode]
                    providers = ["openrouter"]
                    '''
                )
            )
            environment, capture, _ = self.fake_environment(root)
            result = subprocess.run(
                [
                    str(ROOT / "run-exoshell-agent.sh"), "--config", str(config), "--agent", "opencode",
                    str(project), "--", "--model", "model with spaces",
                ],
                cwd=root, env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            arguments = capture.read_text().splitlines()
            self.assertEqual(arguments[arguments.index("--policy") + 1], str(policy))
            self.assertIn("GITLAB_HOST=gitlab.example.com", arguments)
            self.assertIn("common", arguments)
            self.assertIn("openrouter", arguments)
            self.assertIn("opencode", arguments)
            self.assertIn("--no-keep", arguments)
            self.assertNotIn("--name", arguments)
            labels = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--label"]
            self.assertEqual(
                labels,
                ["managed-by=exoshell", "project=project", "agent=opencode"],
            )
            self.assertEqual(arguments[-2:], ["--model", "model with spaces"])
            driver = next(value for value in arguments if value.startswith("--driver-config-json="))
            mount_data = json.loads(driver.split("=", 1)[1])
            self.assertEqual(
                [mount["target"] for mount in mount_data["podman"]["mounts"][1:]],
                [],
            )


class ImageStartupTests(unittest.TestCase):
    HELPER = ROOT / "sandboxes/exoshell-base/exoshell-agent"

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_project_argv_and_exit_status_without_gws(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            project = Path(temporary) / "project with spaces"
            project.mkdir()
            environment = os.environ.copy()
            environment.pop("EXOSHELL_GWS", None)
            for key in ("GWS_CLIENT_ID", "GWS_CLIENT_SECRET", "GWS_REFRESH_TOKEN"):
                environment.pop(key, None)
            result = subprocess.run(
                [str(self.HELPER), str(project), "--", sys.executable, "-c",
                 "import json,os,sys; print(json.dumps([os.getcwd(),sys.argv[1:]]))",
                 "model with spaces", "$(touch nope)"],
                env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [str(project), ["model with spaces", "$(touch nope)"]])
            status = subprocess.run(
                [str(self.HELPER), str(project), "--", sys.executable, "-c", "import sys; sys.exit(17)"],
                env=environment, capture_output=True, text=True,
            )
            self.assertEqual(status.returncode, 17)

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_rejects_project_outside_workspace_and_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            escape = Path(temporary) / "escape"
            escape.symlink_to("/tmp", target_is_directory=True)
            for project in ("relative", "/tmp", str(escape)):
                with self.subTest(project=project):
                    result = subprocess.run(
                        [str(self.HELPER), project, "--", "/bin/true"],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("PROJECT", result.stderr)

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_gws_opt_in_fails_before_running_command(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            marker = Path(temporary) / "started"
            environment = os.environ.copy()
            environment["EXOSHELL_GWS"] = "1"
            for key in ("GWS_CLIENT_ID", "GWS_CLIENT_SECRET", "GWS_REFRESH_TOKEN"):
                environment.pop(key, None)
            result = subprocess.run(
                [str(self.HELPER), temporary, "--", sys.executable, "-c",
                 "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
                env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("GWS_CLIENT_ID", result.stderr)
            self.assertFalse(marker.exists())

    def test_gws_credentials_are_valid_private_json(self) -> None:
        initialize_gws = runpy.run_path(str(self.HELPER))["initialize_gws"]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            directory.chmod(0o777)
            values = {
                "GWS_CLIENT_ID": 'id"\\\nline',
                "GWS_CLIENT_SECRET": "secret with 'quotes' and $(syntax)",
                "GWS_REFRESH_TOKEN": "refresh\tvalue",
            }
            initialize_gws(values, directory)
            credentials = directory / "credentials.json"
            self.assertEqual(
                json.loads(credentials.read_text()),
                {"type": "authorized_user", "client_id": values["GWS_CLIENT_ID"],
                 "client_secret": values["GWS_CLIENT_SECRET"],
                 "refresh_token": values["GWS_REFRESH_TOKEN"]},
            )
            self.assertEqual(credentials.stat().st_mode & 0o777, 0o600)
            config_dir = directory / "config"
            self.assertTrue(config_dir.is_dir())
            self.assertEqual(config_dir.stat().st_mode & 0o777, 0o700)
            self.assertEqual(directory.stat().st_mode & 0o777, 0o777)
            self.assertEqual(values["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"], str(config_dir))
            self.assertEqual(values["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"], str(credentials))
            self.assertEqual(set(directory.iterdir()), {config_dir, credentials})

            config_dir.chmod(0o755)
            initialize_gws(values, directory)
            self.assertEqual(config_dir.stat().st_mode & 0o777, 0o700)

    def test_gws_missing_keys_fail_without_file_or_value_disclosure(self) -> None:
        initialize_gws = runpy.run_path(str(self.HELPER))["initialize_gws"]
        with tempfile.TemporaryDirectory() as temporary:
            values = {"GWS_CLIENT_ID": "sensitive-value", "GWS_CLIENT_SECRET": ""}
            with mock.patch("sys.stderr") as stderr, self.assertRaises(SystemExit) as error:
                initialize_gws(values, Path(temporary))
            self.assertEqual(error.exception.code, 2)
            message = "".join(str(call) for call in stderr.write.call_args_list)
            self.assertIn("GWS_CLIENT_SECRET", message)
            self.assertIn("GWS_REFRESH_TOKEN", message)
            self.assertNotIn("sensitive-value", message)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_gws_failed_rename_leaves_no_partial_file(self) -> None:
        initialize_gws = runpy.run_path(str(self.HELPER))["initialize_gws"]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            values = dict.fromkeys(("GWS_CLIENT_ID", "GWS_CLIENT_SECRET", "GWS_REFRESH_TOKEN"), "opaque")
            with mock.patch("os.replace", side_effect=OSError("failed")), \
                 mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                initialize_gws(values, directory)
            self.assertEqual(list(directory.iterdir()), [directory / "config"])

if __name__ == "__main__":
    unittest.main()
