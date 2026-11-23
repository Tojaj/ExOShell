from __future__ import annotations

import io
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import exoshell_agent as launcher

install = runpy.run_path(str(ROOT / "sandboxes/exoshell-base/exoshell-agent"))[
    "initialize_instructions"
]


class UserInstructionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        config_dir = self.root / "config"
        config_dir.mkdir()
        self.config = config_dir / "example.toml"
        self.config.write_text(
            'instructions = ["guides"]\ninstruction_text = """one\ntwo"""\n'
        )
        self.guides = config_dir / "guides"
        self.guides.mkdir()
        for name in ("z.md", "a.md", "ignored.txt"):
            (self.guides / name).write_text(name + "\n")

    def snapshot(self, *args):
        value = None
        snapshot = None

        def launch(settings, agent_args):
            nonlocal value, snapshot
            snapshot = settings.get("instruction_snapshot")
            if snapshot:
                value = snapshot.read_text()
                self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
                mounts = launcher.mount_config(settings)["podman"]["mounts"]
                self.assertTrue(
                    any(
                        m["source"] == str(snapshot) and m["read_only"]
                        for m in mounts
                        if m["type"] == "bind"
                    )
                )
                command = launcher.create_command(settings, agent_args, None, None)
                self.assertIn("EXOSHELL_IMPORT_INSTRUCTIONS=1", command)
                self.assertNotIn("private literal", str(command))
            return 0

        with mock.patch.object(launcher, "launch", side_effect=launch):
            launcher.run(
                ["--no-policy", "--no-share", "--config", str(self.config), *args],
                cwd=self.root,
            )
        if snapshot:
            self.assertFalse(snapshot.exists())
        return value

    def test_order_overrides_and_suppression(self):
        self.assertEqual(self.snapshot(), "a.md\n\nz.md\n\none\ntwo\n")
        self.config.write_text('instructions = ["missing"]')
        (self.root / "plain").write_text("file")
        self.assertEqual(self.snapshot("--instruction", "plain"), "file\n")
        self.assertEqual(self.snapshot("--instruction-text", "only"), "only\n")
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(
                self.snapshot(
                    "-v",
                    "--instruction-text",
                    "private literal",
                    "--instruction",
                    "plain",
                    "--instruction-text",
                    "last",
                ),
                "private literal\n\nfile\n\nlast\n",
            )
            self.assertNotIn("private literal", stderr.getvalue())
            self.assertIn(str(self.root / "plain"), stderr.getvalue())
        self.assertIsNone(self.snapshot("--no-instructions"))
        with self.assertRaises(launcher.LauncherError):
            self.snapshot("--no-instructions", "--instruction-text", "conflict")

    def test_invalid_config_types(self):
        for entry in (
            'instructions = "one"',
            'instructions = [" "]',
            'instruction_text = ["one"]',
            'instruction_text = ""',
        ):
            self.config.write_text(entry)
            with self.subTest(entry=entry), self.assertRaises(launcher.LauncherError):
                self.snapshot()

    def test_unreadable_file(self):
        source = self.root / "restricted"
        source.touch()
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path == source:
                raise PermissionError(f"permission denied: {source}")
            return original(path, *args, **kwargs)

        with (
            mock.patch.object(Path, "read_text", read),
            self.assertRaisesRegex(launcher.LauncherError, "permission denied"),
        ):
            self.snapshot("--instruction", str(source))

    def test_source_errors_before_launch(self):
        (self.root / "empty").mkdir()
        (self.root / "invalid").write_bytes(b"\xff")
        os.mkfifo(self.root / "fifo")
        for name in ("empty", "missing", "invalid", "fifo"):
            with self.subTest(name=name), self.assertRaises(launcher.LauncherError):
                self.snapshot("--instruction", name)

    def test_personal_guidance_preserved_on_import_and_retry(self):
        snapshot = self.root / "snapshot"
        snapshot.write_text("user guidance\n")
        for agent, relative in (
            ("codex", ".codex/AGENTS.md"),
            ("claude", ".claude/CLAUDE.md"),
            ("opencode", ".config/opencode/AGENTS.md"),
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True)
            target.write_text("existing guidance\n")
            for _ in range(2):
                env = {"HOME": str(self.root), "EXOSHELL_IMPORT_INSTRUCTIONS": "1"}
                install(agent, env, snapshot)
                self.assertNotIn("EXOSHELL_IMPORT_INSTRUCTIONS", env)
                self.assertEqual(
                    target.read_text(), "existing guidance\n\nuser guidance\n"
                )

    def test_codex_global_override(self):
        directory = self.root / "codex"
        directory.mkdir()
        override = directory / "AGENTS.override.md"
        override.write_text("override")
        snapshot = self.root / "snapshot"
        snapshot.write_text("extra\n")
        install(
            "codex",
            {"CODEX_HOME": str(directory), "EXOSHELL_IMPORT_INSTRUCTIONS": "1"},
            snapshot,
        )
        self.assertEqual(override.read_text(), "override\n\nextra\n")
