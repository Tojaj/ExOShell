from __future__ import annotations

import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import exoshell_agent as launcher

STARTUP = runpy.run_path(str(ROOT / "sandboxes/exoshell-base/exoshell-agent"))
INITIALIZE = STARTUP["initialize_skills"]


class SkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def skill(self, name: str) -> Path:
        directory = self.root / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("---\nname: example\ndescription: Example skill\n---\nHello\n")
        return directory

    def settings(self, *arguments: str, config: dict | None = None) -> dict:
        args = launcher.parser().parse_args(["--no-policy", *arguments])
        return launcher.resolve_settings(args, config or {}, cwd=self.root)

    def test_configuration_paths_overrides_and_opt_out(self) -> None:
        config_file = self.root / "config.toml"
        config_file.write_text('skills = ["relative", "~/skills"]\n')
        config = launcher.load_config(config_file, required=True)
        self.assertEqual(config["skills"], [self.root / "relative", Path.home() / "skills"])
        self.assertEqual(self.settings(config=config)["skills"], config["skills"])
        self.assertEqual(self.settings("--skill", "one", "--skill", "two", config=config)["skills"],
                         [self.root / "one", self.root / "two"])
        self.assertEqual(self.settings("--no-skills", config=config)["skills"], [])
        self.assertEqual(self.settings()["skills"], [])
        for value in ('"path"', '[""]', '[" "]', '[42]', 'true'):
            config_file.write_text(f"skills = {value}\n")
            with self.subTest(value=value), self.assertRaises(launcher.LauncherError):
                launcher.load_config(config_file, required=True)

    def test_collection_individual_and_symlink_aliases(self) -> None:
        collection = self.root / "collection"
        collection.mkdir()
        first = self.skill("collection/first")
        external = self.skill("external")
        alias = collection / "alias"
        alias.symlink_to(external)
        (collection / "README.md").write_text("Collection description")
        self.skill("collection/unrelated/nested")
        self.assertEqual(launcher.select_skills([collection]), {"alias": alias, "first": first})
        self.assertEqual(launcher.select_skills([alias]), {"alias": alias})
        self.assertEqual(self.settings("--skill", str(alias))["skills"], [alias])
        empty = self.root / "empty"
        empty.mkdir()
        self.assertEqual(launcher.select_skills([empty]), {})

    def test_duplicate_names_and_invalid_sources(self) -> None:
        first = self.skill("one/review")
        second = self.skill("two/review")
        with self.assertRaisesRegex(launcher.LauncherError, "duplicate skill 'review'"):
            launcher.select_skills([first, second])
        invalid = self.root / "invalid"
        invalid.mkdir()
        (invalid / "SKILL.md").mkdir()
        broken = self.root / "broken"
        broken.symlink_to(self.root / "missing")
        for source in (self.root / "missing", first / "SKILL.md", invalid, broken):
            with self.subTest(source=source), self.assertRaises(launcher.LauncherError):
                launcher.select_skills([source])

    def test_imports_apply_to_every_agent_and_preserve_forwarded_arguments(self) -> None:
        source = self.skill("skill")
        for agent in launcher.AGENTS:
            with self.subTest(agent=agent):
                settings = self.settings("--agent", agent, "--no-share", "--skill", str(source))
                settings["skills_snapshot"] = source.parent
                forwarded = ["--", "literal $(syntax)"]
                command = launcher.create_command(settings, forwarded, None, None)
                self.assertEqual(command[-2:], forwarded)
                self.assertIn(launcher.AGENTS[agent]["executable"], command)
                self.assertEqual(settings["skills"], [source])

    def test_snapshot_dereferences_links_and_preserves_executable_scripts(self) -> None:
        source = self.skill("skill")
        external = self.root / "external"
        external.mkdir()
        script = external / "script.sh"
        script.write_text("#!/bin/sh\necho example\n")
        script.chmod(0o755)
        (source / "scripts").symlink_to(external)
        (source / "reference.txt").symlink_to(script)
        snapshot = self.root / "snapshot"
        launcher.copy_skill_snapshot(source, snapshot)
        self.assertFalse((snapshot / "scripts").is_symlink())
        self.assertFalse((snapshot / "reference.txt").is_symlink())
        self.assertEqual((snapshot / "scripts/script.sh").read_text(), script.read_text())
        self.assertEqual((snapshot / "scripts/script.sh").stat().st_mode & 0o111, 0o111)
        script.write_text("Changed after snapshot")
        self.assertNotEqual((snapshot / "reference.txt").read_text(), script.read_text())

    def test_snapshot_rejects_cycles_broken_links_special_and_unreadable_files(self) -> None:
        for kind in ("cycle", "broken", "fifo", "unreadable"):
            with self.subTest(kind=kind):
                source = self.skill(kind)
                entry = source / "support"
                if kind == "cycle":
                    entry.symlink_to(source)
                elif kind == "broken":
                    entry.symlink_to(self.root / "missing")
                elif kind == "fifo":
                    os.mkfifo(entry)
                else:
                    entry.write_text("Private")
                    entry.chmod(0)
                try:
                    if kind == "unreadable" and os.getuid() == 0:
                        continue
                    with self.assertRaises(launcher.LauncherError):
                        launcher.copy_skill_snapshot(source, self.root / f"snapshot-{kind}")
                finally:
                    if kind == "unreadable":
                        entry.chmod(0o600)

    def test_launch_snapshot_lifetime_no_share_keep_and_failure_cleanup(self) -> None:
        source = self.skill("skill")
        for result in (0, 7, KeyboardInterrupt()):
            snapshot = None

            def launch(settings: dict, arguments: list) -> int:
                nonlocal snapshot
                snapshot = settings["skills_snapshot"]
                self.assertTrue((snapshot / "skill/SKILL.md").is_file())
                command = launcher.create_command(settings, arguments, None, None)
                driver = next(value for value in command if value.startswith("--driver-config-json="))
                mounts = json.loads(driver.split("=", 1)[1])["podman"]["mounts"]
                self.assertEqual([mount["type"] for mount in mounts], ["bind", "tmpfs"])
                self.assertTrue(mounts[0]["read_only"])
                self.assertEqual(mounts[0]["target"], launcher.CONTAINER_SKILLS_SNAPSHOT)
                self.assertNotIn("--no-keep", command)
                self.assertIn("EXOSHELL_SKILLS_SNAPSHOT=/tmp/exoshell-skills", command)
                self.assertIn("/bin/sh", command)
                if isinstance(result, BaseException):
                    raise result
                return result

            with mock.patch.object(launcher, "launch", side_effect=launch):
                arguments = ["--no-policy", "--no-share", "--keep", "--skill", str(source)]
                if isinstance(result, BaseException):
                    with self.assertRaises(KeyboardInterrupt):
                        launcher.run(arguments, cwd=self.root)
                else:
                    self.assertEqual(launcher.run(arguments, cwd=self.root), result)
            self.assertFalse(snapshot.exists())

    def test_invalid_snapshot_stops_before_launch_and_is_cleaned(self) -> None:
        source = self.skill("skill")
        (source / "broken").symlink_to(self.root / "missing")
        destinations = []
        original = launcher.copy_skill_snapshot

        def copy(source: Path, destination: Path, *arguments: object) -> None:
            destinations.append(destination)
            original(source, destination, *arguments)

        with mock.patch.object(launcher, "copy_skill_snapshot", side_effect=copy), \
             mock.patch.object(launcher, "launch") as launch:
            with self.assertRaises(launcher.LauncherError):
                launcher.run(["--no-policy", "--skill", str(source)], cwd=self.root)
            launch.assert_not_called()
        self.assertFalse(destinations[0].parent.exists())

    def test_disabled_sources_are_not_inspected_and_verbose_reports_paths(self) -> None:
        config = self.root / "config.toml"
        config.write_text('skills = ["missing"]\n')
        with mock.patch.object(launcher, "launch", return_value=0), \
             mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            launcher.run(["--config", str(config), "--no-policy", "--no-skills", "-v"], cwd=self.root)
            self.assertIn("exoshell: skills = []", stderr.getvalue())
            source = self.skill("skill")
            stderr.seek(0)
            stderr.truncate()
            launcher.run(["--no-policy", "--skill", str(source), "-v"], cwd=self.root)
            self.assertIn(f"exoshell: skills = {json.dumps([str(source)])}", stderr.getvalue())

    def test_old_image_gate_fails_clearly_and_supported_image_executes(self) -> None:
        settings = self.settings()
        settings["skills_snapshot"] = self.root
        command = launcher.create_command(settings, [], None, None)
        start = command.index("/bin/sh")
        gate = command[start:start + 4]
        marker = self.root / "capability"
        gate[2] = gate[2].replace("/etc/exoshell/skills-import-v1", str(marker))
        invocation = [*gate, "/bin/sh", "-c", "exit 7"]
        result = subprocess.run(invocation, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("rebuild the sandbox image", result.stderr)
        marker.touch()
        self.assertEqual(subprocess.run(invocation).returncode, 7)

    def test_startup_import_preserves_image_skills_and_consumes_setting(self) -> None:
        source = self.skill("snapshot/imported")
        destination = self.root / "destination"
        existing = self.skill("destination/image-skill")
        environment = {"EXOSHELL_SKILLS_SNAPSHOT": str(source.parent), "OTHER": "value"}
        INITIALIZE(environment, destination, source.parent)
        self.assertEqual(environment, {"OTHER": "value"})
        self.assertEqual((destination / "imported/SKILL.md").read_text(), (source / "SKILL.md").read_text())
        self.assertTrue(existing.is_dir())
        (source / "SKILL.md").unlink()
        self.assertTrue((destination / "imported/SKILL.md").is_file())
        INITIALIZE({}, destination, source.parent)

    def test_startup_collision_preflights_every_skill_including_dangling_targets(self) -> None:
        source = self.skill("snapshot/a-new")
        self.skill("snapshot/z-collision")
        destination = self.root / "destination"
        destination.mkdir()
        (destination / "z-collision").symlink_to(self.root / "missing")
        with mock.patch.dict(INITIALIZE.__globals__, {"fail": mock.Mock(side_effect=SystemExit(2))}) as namespace:
            with self.assertRaises(SystemExit):
                INITIALIZE({"EXOSHELL_SKILLS_SNAPSHOT": str(source.parent)}, destination, source.parent)
            self.assertIn("conflicts", namespace["fail"].call_args.args[0])
        self.assertFalse((destination / "a-new").exists())

    def test_startup_copy_failure_stops_before_agent_execution(self) -> None:
        source = self.skill("snapshot/imported")
        destination = self.root / "destination"
        with mock.patch.dict(STARTUP["main"].__globals__, {
            "WORKSPACE": self.root,
            "initialize_skills": lambda env: INITIALIZE(env, destination, source.parent),
        }), mock.patch.dict(os.environ, {"EXOSHELL_SKILLS_SNAPSHOT": str(source.parent)}), \
             mock.patch.object(INITIALIZE.__globals__["shutil"], "copytree", side_effect=OSError("copy failed")), \
             mock.patch.object(os, "execvpe") as execute, \
             mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                STARTUP["main"]([str(self.root), "--", "codex"])
            execute.assert_not_called()

    def test_image_has_one_claude_directory_link_and_explicit_policy_permission(self) -> None:
        dockerfile = (ROOT / "sandboxes/exoshell-base/Dockerfile").read_text()
        self.assertIn("ln -s ../.agents/skills /sandbox/.claude/skills", dockerfile)
        self.assertIn("touch /etc/exoshell/skills-import-v1", dockerfile)
        self.assertIn("- /sandbox/.agents/skills", (ROOT / "policies/policy.yaml").read_text())
        skills = self.skill("home/.agents/skills/example")
        claude = self.root / "home/.claude"
        claude.mkdir()
        (claude / "skills").symlink_to("../.agents/skills")
        self.assertEqual((claude / "skills/example/SKILL.md").resolve(), skills / "SKILL.md")

    @unittest.skipUnless(shutil.which("claude"), "Claude Code is not installed")
    def test_installed_claude_discovers_skill_through_directory_symlink(self) -> None:
        home = self.root / "home"
        skills = self.skill("home/.agents/skills/snapshot-probe")
        marker = "EXOSHELL_SKILL_SYMLINK_MARKER"
        (skills / "SKILL.md").write_text(
            "---\nname: snapshot-probe\ndescription: Test personal skill\n---\n" + marker + "\n"
        )
        claude = home / ".claude"
        claude.mkdir()
        (claude / "skills").symlink_to("../.agents/skills")
        messages = []
        received = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                payload = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path.split("?", 1)[0].rstrip("/").endswith("/messages"):
                    messages.append(json.loads(payload))
                # Discovery happens before inference; no model or real credentials are needed.
                response = json.dumps({"type": "error", "error": {
                    "type": "authentication_error", "message": "Test stops after skill discovery",
                }}).encode()
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                if messages:
                    received.set()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            environment = {"PATH": os.environ["PATH"], "HOME": str(home),
                           "CLAUDE_CONFIG_DIR": str(claude), "ANTHROPIC_API_KEY": "test-placeholder",
                           "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                           "DISABLE_NONESSENTIAL_TRAFFIC": "1"}
            with subprocess.Popen(["claude", "--print", "--no-session-persistence",
                                   "--model", "claude-sonnet-4-6", "/snapshot-probe"],
                                  env=environment, cwd=self.root,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                try:
                    self.assertTrue(received.wait(10), "Claude did not reach the local inference stub")
                finally:
                    process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
            self.assertIn(marker, json.dumps(messages), "Claude did not expand the symlinked skill")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
