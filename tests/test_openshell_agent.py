from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import runpy
import shutil
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
            "removed-gws-true": "gws = true\n",
            "removed-gws-false": "gws = false\n",
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


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cwd = self.root / "caller"
        self.home = self.root / "home"
        self.cwd.mkdir()
        self.home.mkdir()
        self.local = self.cwd / ".exoshell.local.toml"
        self.user = self.home / ".config/exoshell/exoshell.local.toml"
        self.system = self.root / "etc/exoshell/exoshell.local.toml"
        self.user.parent.mkdir(parents=True)
        self.system.parent.mkdir(parents=True)
        environment = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("XDG_CONFIG_HOME", None)
        system = mock.patch.object(launcher, "SYSTEM_CONFIG_FILE", self.system)
        system.start()
        self.addCleanup(system.stop)

    def command(self, *arguments: str) -> list[str]:
        with mock.patch.object(launcher, "git_identity", return_value=("Test", "test@example.com")), \
             mock.patch.object(launcher.subprocess, "run", return_value=mock.Mock(returncode=0)) as execute:
            self.assertEqual(launcher.run(arguments, cwd=self.cwd), 0)
        return execute.call_args.args[0]

    def assert_policy_rejected_before_subprocesses(self, arguments: list[str], message: str) -> None:
        with mock.patch.object(launcher, "git_identity") as identity, \
             mock.patch.object(launcher.subprocess, "run") as execute:
            with self.assertRaisesRegex(launcher.LauncherError, message):
                launcher.run(arguments, cwd=self.cwd)
            identity.assert_not_called()
            execute.assert_not_called()

    def test_missing_policy_stops_launch_without_config_or_with_partial_config(self) -> None:
        for content in (None, "", 'image = "registry.example/local"\n'):
            with self.subTest(content=content):
                if content is not None:
                    self.local.write_text(content)
                self.assert_policy_rejected_before_subprocesses([], "no sandbox policy selected")
        with mock.patch.object(sys, "argv", ["run-exoshell-agent.sh"]), \
             mock.patch.object(Path, "cwd", return_value=self.cwd), \
             mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr, \
             mock.patch.object(launcher.subprocess, "run") as execute:
            self.assertEqual(launcher.main(), 2)
            execute.assert_not_called()
        for remedy in ("--policy PATH", "'policy'", "--no-policy"):
            self.assertIn(remedy, stderr.getvalue())

    def test_invalid_selected_policy_paths_stop_before_subprocesses(self) -> None:
        directory = self.cwd / "directory.yaml"
        directory.mkdir()
        dangling = self.cwd / "dangling.yaml"
        dangling.symlink_to(self.cwd / "missing.yaml")
        for path in (self.cwd / "missing.yaml", directory, dangling):
            for source in ("cli", "discovered", "explicit"):
                with self.subTest(path=path, source=source):
                    if self.local.exists():
                        self.local.unlink()
                    if source == "cli":
                        arguments = ["--policy", path.name]
                    else:
                        self.local.write_text(f'policy = "{path.name}"\n')
                        arguments = ["--config", str(self.local)] if source == "explicit" else []
                    self.assert_policy_rejected_before_subprocesses(
                        arguments, "policy file does not exist"
                    )

    def test_valid_policy_paths_resolve_relative_to_source_and_follow_symlinks(self) -> None:
        cli_policy = self.cwd / "policy with spaces.yaml"
        cli_policy.write_text("network_policies: {}\n")
        configured_policy = self.user.parent / cli_policy.name
        configured_policy.write_text("network_policies: {}\n")
        cli_link = self.cwd / "linked.yaml"
        cli_link.symlink_to(cli_policy)
        config_link = self.user.parent / cli_link.name
        config_link.symlink_to(configured_policy)
        for relative in (cli_policy.name, cli_link.name):
            with self.subTest(relative=relative):
                command = self.command("--policy", relative)
                self.assertEqual(command[command.index("--policy") + 1], str(cli_policy))
                self.user.write_text(f'policy = "{relative}"\n')
                command = self.command("--config", str(self.user))
                self.assertEqual(command[command.index("--policy") + 1], str(configured_policy))

    def test_cli_policy_override_and_opt_out_ignore_invalid_configured_path(self) -> None:
        self.local.write_text('policy = "missing.yaml"\n')
        replacement = self.cwd / "replacement.yaml"
        replacement.write_text("network_policies: {}\n")
        command = self.command("--policy", replacement.name)
        self.assertEqual(command[command.index("--policy") + 1], str(replacement))
        self.assertNotIn("--policy", self.command("--no-policy"))
        self.local.unlink()
        self.assertNotIn("--policy", self.command("--no-policy"))

    def test_each_location_and_precedence_then_defaults(self) -> None:
        for name, path in (("caller", self.local), ("user", self.user), ("system", self.system)):
            path.write_text(f'image = "registry.example/{name}"\n')
        for name, path in (("caller", self.local), ("user", self.user), ("system", self.system)):
            with self.subTest(location=name):
                self.assertEqual(launcher.discover_config(None, cwd=self.cwd), path)
                self.assertIn(f"registry.example/{name}", self.command("--no-policy"))
                path.unlink()
        self.assertIsNone(launcher.discover_config(None, cwd=self.cwd))
        command = self.command("--no-policy")
        self.assertIn(launcher.DEFAULTS["image"], command)
        self.assertIn("exoshell-codex", command)

    def test_explicit_arbitrary_filename_relative_absolute_and_missing(self) -> None:
        # Even an invalid discovery candidate must not affect explicit selection.
        self.local.mkdir()
        explicit = self.cwd / "settings.data"
        explicit.write_text('image = "registry.example/explicit"\n')
        for argument in (explicit.name, str(explicit)):
            with self.subTest(argument=argument):
                self.assertEqual(launcher.discover_config(Path(argument), cwd=self.cwd), explicit)
                self.assertIn("registry.example/explicit", self.command("--no-policy", "--config", argument))
        self.user.write_text('image = "registry.example/user"\n')
        with self.assertRaisesRegex(launcher.LauncherError, "does not exist"):
            self.command("--config", "missing.toml")

    def test_xdg_absolute_override_and_unset_empty_relative_fallbacks(self) -> None:
        self.user.write_text("")
        override = self.root / "xdg/exoshell/exoshell.local.toml"
        override.parent.mkdir(parents=True)
        override.write_text("")
        for value in (None, "", "relative", "~/config", str(override.parents[1])):
            with self.subTest(value=value):
                if value is None:
                    os.environ.pop("XDG_CONFIG_HOME", None)
                else:
                    os.environ["XDG_CONFIG_HOME"] = value
                expected = override if value == str(override.parents[1]) else self.user
                self.assertEqual(launcher.discover_config(None, cwd=self.cwd), expected)

    def test_empty_and_partial_configs_do_not_inherit(self) -> None:
        self.user.write_text('agent = "claude"\nimage = "registry.example/user"\nproviders = ["user"]\n')
        self.system.write_text('github_host = "system.example.com"\n')
        for content, image in (("", launcher.DEFAULTS["image"]),
                               ('image = "registry.example/local"\n', "registry.example/local")):
            with self.subTest(content=content):
                self.local.write_text(content)
                command = self.command("--no-policy")
                self.assertIn(image, command)
                self.assertIn("codex", command)
                self.assertIn("exoshell-codex", command)
                self.assertNotIn("user", command)
                self.assertFalse(any(value.startswith("GH_HOST=") for value in command))

    def test_invalid_configs_at_each_location_stop_launch(self) -> None:
        for path in (self.local, self.user, self.system):
            for content in ('image = [', 'unknown = "value"\n'):
                with self.subTest(path=path, content=content):
                    path.write_text(content)
                    with self.assertRaises(launcher.LauncherError):
                        self.command()
                    path.unlink()

    def test_directory_fifo_and_dangling_symlink_stop_launch(self) -> None:
        self.user.write_text("")
        self.local.mkdir()
        with self.assertRaisesRegex(launcher.LauncherError, "not a file"):
            self.command()
        self.local.rmdir()
        os.mkfifo(self.local)
        with self.assertRaisesRegex(launcher.LauncherError, "not a file"):
            self.command()
        self.local.unlink()
        self.local.symlink_to(self.cwd / "missing.toml")
        with self.assertRaisesRegex(launcher.LauncherError, "does not exist"):
            self.command()

    def test_invalid_utf8_and_symlink_loop_are_actionable(self) -> None:
        self.user.write_text("")
        self.local.write_bytes(b'\xff')
        with self.assertRaisesRegex(launcher.LauncherError, "cannot load configuration"):
            self.command()
        self.local.unlink()
        self.local.symlink_to(self.local)
        with self.assertRaisesRegex(launcher.LauncherError, "cannot (resolve|inspect) configuration"):
            self.command()

    def test_inspection_and_read_permission_errors_are_actionable(self) -> None:
        self.local.write_text("")
        self.user.write_text("")
        with mock.patch.object(Path, "lstat", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(launcher.LauncherError, "cannot inspect configuration"):
                self.command()
        with mock.patch.object(Path, "stat", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(launcher.LauncherError, "cannot inspect configuration"):
                self.command()
        with mock.patch.object(Path, "open", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(launcher.LauncherError, "cannot load configuration"):
                self.command()

    def test_non_directory_ancestor_is_an_error(self) -> None:
        blocked = self.root / "blocked"
        blocked.write_text("")
        os.environ["XDG_CONFIG_HOME"] = str(blocked)
        with self.assertRaisesRegex(launcher.LauncherError, "cannot inspect configuration"):
            self.command()

    def test_selected_config_paths_provider_composition_and_cli_overrides(self) -> None:
        policy = self.user.parent / "policy.yaml"
        policy.write_text("network_policies: {}\n")
        kubeconfig = self.user.parent / "kubeconfig"
        kubeconfig.write_text("")
        project = self.user.parent / "source/project"
        project.mkdir(parents=True)
        self.user.write_text(
            'image = "registry.example/user"\npolicy = "policy.yaml"\n'
            'host_share = "source"\nkubeconfig = "kubeconfig"\nproviders = ["common"]\n'
            '[agents.claude]\nproviders = ["claude-api"]\n'
        )
        command = self.command("--agent", "claude", str(project))
        self.assertIn(str(policy), command)
        self.assertIn("common", command)
        self.assertIn("claude-api", command)
        driver = next(value for value in command if value.startswith("--driver-config-json="))
        mounts = json.loads(driver.split("=", 1)[1])["podman"]["mounts"]
        self.assertEqual(mounts[0]["source"], str(project.parent))
        self.assertEqual(mounts[1]["source"], str(kubeconfig))
        self.assertIn("/workspace/project", command)
        cli_policy = self.cwd / "cli.yaml"
        cli_policy.write_text("")
        command = self.command(
            "--image", "registry.example/cli", "--policy", "cli.yaml", "--no-kubeconfig",
            "--provider", "replacement", str(project),
        )
        self.assertIn("registry.example/cli", command)
        self.assertIn(str(cli_policy), command)
        self.assertIn("replacement", command)
        self.assertNotIn("common", command)
        self.assertNotIn("exoshell-codex", command)

    def test_no_parent_uppercase_or_xdg_config_dirs_search(self) -> None:
        (self.cwd.parent / ".exoshell.local.toml").write_text("")
        uppercase = self.home / ".config/ExOShell/exoshell.local.toml"
        uppercase.parent.mkdir()
        uppercase.write_text("")
        extra = self.root / "extra/exoshell/exoshell.local.toml"
        extra.parent.mkdir(parents=True)
        extra.write_text("")
        os.environ["XDG_CONFIG_DIRS"] = str(extra.parents[1])
        self.assertIsNone(launcher.discover_config(None, cwd=self.cwd))

    def verbose_values(self, *arguments: str) -> dict[str, object]:
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr, \
             mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
            self.command(*arguments)
            self.assertEqual(stdout.getvalue(), "")
        return {
            key: json.loads(value)
            for key, value in (
                line.removeprefix("exoshell: ").split(" = ", 1)
                for line in stderr.getvalue().splitlines()
            )
        }

    def test_verbose_aliases_defaults_and_silent_normal_launch(self) -> None:
        self.assertEqual(self.verbose_values("--no-policy"), {})
        expected = {
            "config": "built-in defaults", "agent": "codex",
            "model": None, "effort": None,
            "image": launcher.DEFAULTS["image"], "providers": ["exoshell-codex"],
            "policy": None, "kubeconfig": None, "github_host": None,
            "gitlab_host": None, "keep": False, "host_share": str(self.cwd),
            "project": str(self.cwd), "container_project": "/workspace",
        }
        for arguments in (("-v",), ("--verbose",), ("-v", "--verbose")):
            with self.subTest(arguments=arguments):
                values = self.verbose_values("--no-policy", *arguments)
                self.assertEqual(values, expected)
                self.assertEqual(list(values), list(expected))

    def test_verbose_selected_discovered_and_explicit_config_paths(self) -> None:
        for path in (self.local, self.user, self.system):
            path.write_text('image = "registry.example/test"\n')
        for path in (self.local, self.user, self.system):
            with self.subTest(path=path):
                self.assertEqual(self.verbose_values("-v", "--no-policy")["config"], str(path))
                path.unlink()
        explicit = self.cwd / "custom config.toml"
        explicit.write_text('image = "registry.example/explicit"\n')
        link = self.cwd / "linked.toml"
        link.symlink_to(explicit)
        values = self.verbose_values("--verbose", "--no-policy", "--config", link.name)
        self.assertEqual(values["config"], str(explicit))
        self.assertEqual(values["image"], "registry.example/explicit")

    def test_verbose_effective_paths_providers_overrides_and_clearing(self) -> None:
        project = self.cwd / 'share with spaces' / 'project "quoted"'
        project.mkdir(parents=True)
        policy = self.user.parent / "policy.yaml"
        policy.write_text("")
        kubeconfig = self.user.parent / "kubeconfig"
        kubeconfig.write_text("private contents")
        self.user.write_text(
            f'host_share = "{project.parent}"\n'
            'policy = "policy.yaml"\nkubeconfig = "kubeconfig"\n'
            'github_host = "github.example.com"\ngitlab_host = "gitlab.example.com"\n'
            'providers = ["common"]\n[agents.claude]\nproviders = ["claude-api"]\n'
        )
        values = self.verbose_values("-v", "--agent", "claude", str(project))
        self.assertEqual(values["agent"], "claude")
        self.assertEqual(values["providers"], ["common", "claude-api"])
        self.assertEqual(values["policy"], str(policy))
        self.assertEqual(values["kubeconfig"], str(kubeconfig))
        self.assertEqual(values["project"], str(project))
        self.assertEqual(values["host_share"], str(project.parent))
        self.assertEqual(values["container_project"], '/workspace/project "quoted"')
        values = self.verbose_values(
            "-v", "--image", "registry.example/cli", "--provider", "replacement",
            "--keep", "--no-policy", "--no-kubeconfig", "--no-github-host",
            "--gitlab-host", "cli.example.com", "--host-share", ".", str(project),
        )
        self.assertEqual(values["image"], "registry.example/cli")
        self.assertEqual(values["providers"], ["replacement"])
        self.assertTrue(values["keep"])
        for key in ("policy", "kubeconfig", "github_host"):
            self.assertIsNone(values[key])
        self.assertEqual(values["gitlab_host"], "cli.example.com")
        self.assertEqual(values["host_share"], str(self.cwd))
        self.assertEqual(self.verbose_values("-v", "--no-providers", str(project))["providers"], [])

    def test_verbose_reports_selected_config_before_loading_failure(self) -> None:
        self.local.write_text("not valid TOML")
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            with self.assertRaises(launcher.LauncherError):
                launcher.run(["-v"], cwd=self.cwd)
        self.assertEqual(stderr.getvalue(), f'exoshell: config = {json.dumps(str(self.local))}\n')

    def test_verbose_settings_are_flushed_before_image_and_git_checks(self) -> None:
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            def check_output(*args: object) -> mock.Mock:
                self.assertIn('exoshell: container_project = "/workspace"\n', stderr.getvalue())
                return mock.Mock(returncode=0)

            def check_identity(project: Path) -> tuple[str, str]:
                check_output()
                return "Test", "test@example.com"

            with mock.patch.object(launcher.subprocess, "run", side_effect=check_output), \
                 mock.patch.object(launcher, "git_identity", side_effect=check_identity), \
                 mock.patch.object(stderr, "flush", wraps=stderr.flush) as flush:
                self.assertEqual(launcher.run(["-v", "--no-policy"], cwd=self.cwd), 0)
            self.assertEqual(flush.call_count, 14)


class ResolutionTests(unittest.TestCase):
    def parse(self, *arguments: str) -> argparse.Namespace:
        # These tests exercise settings unrelated to policy selection.
        return launcher.parser().parse_args(["--no-policy", *arguments])

    def test_codex_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary).resolve()
            settings = launcher.resolve_settings(self.parse(), {}, cwd=cwd)
            self.assertEqual(settings["agent"], "codex")
            self.assertFalse(settings["keep"])
            self.assertEqual(settings["providers"], ["exoshell-codex"])
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

    def test_removed_gws_options_are_rejected(self) -> None:
        for option in ("--gws", "--no-gws"):
            with self.subTest(option=option), self.assertRaises(SystemExit):
                self.parse(option)

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
                self.assertEqual([mount["target"] for mount in mounts], ["/workspace", "/tmp/gws"])
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

    def test_gws_tmpfs_is_provisioned_without_provider_or_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = self.settings(Path(temporary), "opencode")
            mounts = launcher.mount_config(settings)["podman"]["mounts"]
            self.assertEqual(mounts[-1], {"type": "tmpfs", "target": "/tmp/gws", "mode": 0o777})
            environment = launcher.environment_args(settings, "A User", "a@example.com")
            self.assertNotIn("EXOSHELL_GWS=1", environment)
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
        environment.update({
            "PATH": f"{binaries}:{environment['PATH']}", "CAPTURE": str(capture),
            "HOME": str(root / "home"), "XDG_CONFIG_HOME": str(root / "xdg"),
        })
        return environment, capture, binaries

    def test_verbose_wrapper_preserves_command_and_agent_argument_forwarding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment, capture, _ = self.fake_environment(root)
            environment["EXOSHELL_TEST_SECRET"] = "secret must not be dumped"
            config = root / "launcher.toml"
            config.write_text('image = "localhost/test-image:latest"\n')
            commands = []
            for flags in ([], ["-v"], ["--verbose"]):
                result = subprocess.run(
                    [str(ROOT / "run-exoshell-agent.sh"), "--config", str(config),
                     *flags, "--no-policy", "--", "-v", "--verbose", "private agent argument"],
                    cwd=root, env=environment, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                commands.append(capture.read_text().splitlines())
                self.assertEqual(commands[-1][-3:], ["-v", "--verbose", "private agent argument"])
                if flags:
                    self.assertIn(f'exoshell: config = {json.dumps(str(config))}\n', result.stderr)
                    self.assertIn('exoshell: image = "localhost/test-image:latest"\n', result.stderr)
                    self.assertNotIn("private agent argument", result.stderr)
                    self.assertNotIn(environment["EXOSHELL_TEST_SECRET"], result.stderr)
                else:
                    self.assertEqual(result.stderr, "")
            self.assertEqual(commands[0], commands[1])
            self.assertEqual(commands[0], commands[2])

    def test_wrapper_discovery_uses_caller_not_project_or_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = root / "checkout"
            checkout.joinpath("scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "run-exoshell-agent.sh", checkout)
            shutil.copy2(ROOT / "scripts/exoshell_agent.py", checkout / "scripts")
            # These must be ignored even though both locations contain configs.
            checkout.joinpath(".exoshell.local.toml").write_text('unknown = true\n')
            project = root / "project"
            project.mkdir()
            project.joinpath(".exoshell.local.toml").write_text('unknown = true\n')
            caller = root / "caller"
            caller.mkdir()
            environment, capture, _ = self.fake_environment(root)
            user_config = Path(environment["XDG_CONFIG_HOME"]) / "exoshell/exoshell.local.toml"
            user_config.parent.mkdir(parents=True)
            user_config.write_text('image = "registry.example/user"\n')
            local_config = caller / ".exoshell.local.toml"
            local_config.write_text('image = "localhost/test-image:latest"\n')
            for expected in ("localhost/test-image:latest", "registry.example/user"):
                with self.subTest(expected=expected):
                    result = subprocess.run(
                        [str(checkout / "run-exoshell-agent.sh"), "--no-policy", str(project)],
                        cwd=caller, env=environment, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    arguments = capture.read_text().splitlines()
                    self.assertEqual(arguments[arguments.index("--from") + 1], expected)
                    if local_config.exists():
                        local_config.unlink()

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
                ["/tmp/gws"],
            )


class ImageStartupTests(unittest.TestCase):
    HELPER = ROOT / "sandboxes/exoshell-base/exoshell-agent"

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_project_argv_and_exit_status_without_gws(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            project = Path(temporary) / "project with spaces"
            project.mkdir()
            environment = os.environ.copy()
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
    def test_partial_gws_environment_fails_before_running_command(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            marker = Path(temporary) / "started"
            environment = os.environ.copy()
            for key in ("GWS_CLIENT_ID", "GWS_CLIENT_SECRET", "GWS_REFRESH_TOKEN"):
                environment.pop(key, None)
            environment["GWS_REFRESH_TOKEN"] = "sensitive-value"
            result = subprocess.run(
                [str(self.HELPER), temporary, "--", sys.executable, "-c",
                 "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
                env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("GWS_CLIENT_ID", result.stderr)
            self.assertNotIn("sensitive-value", result.stderr)
            self.assertFalse(marker.exists())

    def test_absent_or_empty_gws_values_skip_without_storage_or_environment_changes(self) -> None:
        initialize_gws = runpy.run_path(str(self.HELPER))["initialize_gws"]
        for credentials in ({}, dict.fromkeys(("GWS_CLIENT_ID", "GWS_CLIENT_SECRET", "GWS_REFRESH_TOKEN"), "")):
            with self.subTest(credentials=credentials), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary) / "missing"
                environment = {**credentials, "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": "/custom/config"}
                expected = environment.copy()
                initialize_gws(environment, directory)
                self.assertFalse(directory.exists())
                self.assertEqual(environment, expected)

    @unittest.skipUnless(os.access("/workspace", os.W_OK), "writable /workspace is required")
    def test_complete_gws_environment_initializes_before_exec_without_opt_in(self) -> None:
        startup = runpy.run_path(str(self.HELPER))
        main = startup["main"]
        initialize_gws = startup["initialize_gws"]
        with tempfile.TemporaryDirectory(dir="/workspace") as temporary:
            project = Path(temporary).resolve()
            directory = project / "gws"
            directory.mkdir()
            environment = {key: f"openshell:resolve:env:{key}" for key in startup["GWS_KEYS"]}
            with mock.patch.dict(os.environ, environment, clear=True), \
                 mock.patch.dict(main.__globals__, {"initialize_gws": lambda env: initialize_gws(env, directory)}), \
                 mock.patch("os.chdir") as chdir, mock.patch("os.execvpe") as execute:
                main([str(project), "--", "/bin/true", "argument with spaces"])
            chdir.assert_called_once_with(project)
            command, arguments, child_environment = execute.call_args.args
            self.assertEqual(command, "/bin/true")
            self.assertEqual(arguments, ["/bin/true", "argument with spaces"])
            self.assertEqual(child_environment["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"],
                             str(directory / "credentials.json"))
            self.assertEqual(child_environment["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"], str(directory / "config"))
            self.assertEqual(json.loads((directory / "credentials.json").read_text())["refresh_token"],
                             environment["GWS_REFRESH_TOKEN"])

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
