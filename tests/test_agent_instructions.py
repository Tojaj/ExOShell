from __future__ import annotations

import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "sandboxes/exoshell-base"
HELPER = IMAGE / "render-agent-instructions.py"
RENDER = runpy.run_path(str(HELPER))["render"]


class AgentInstructionTests(unittest.TestCase):
    def test_render_preserves_template_and_round_trips_markdown(self) -> None:
        template = (IMAGE / "codex.config.toml").read_text(encoding="utf-8")
        first = '# First\nUse "quotes", \'apostrophes\', and """triple quotes""".\n'
        second = '```bash\nrg "\\\\path"\n```\nUnicode: café 🐚\nControl: \t\b\f\x00\x7f\n'
        expected = first.rstrip("\n") + "\n\n" + second.rstrip("\n") + "\n"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            sources = directory / "instructions"
            sources.mkdir()
            (sources / "b.md").write_text(second, encoding="utf-8")
            (sources / "a.md").write_text(first, encoding="utf-8")
            (sources / "ignored.txt").write_text("Do not include")
            codex = directory / "config.toml"
            claude = directory / "claude-code/CLAUDE.md"
            codex.write_text(template, encoding="utf-8")
            RENDER(sources, codex, claude)
            rendered = codex.read_text(encoding="utf-8")
            actual = tomllib.loads(rendered)
            self.assertEqual(actual.pop("developer_instructions"), expected)
            self.assertEqual(actual, tomllib.loads(template))
            self.assertTrue(rendered.endswith(template))
            self.assertEqual(claude.read_text(encoding="utf-8"), expected)
            for path in (codex, claude):
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_existing_instructions_and_missing_sources_fail_before_writes(self) -> None:
        for template, has_sources in (("developer_instructions = ''\n", True), ("", False)):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                sources = directory / "instructions"
                sources.mkdir()
                if has_sources:
                    (sources / "a.md").write_text("New guidance")
                codex = directory / "config.toml"
                claude = directory / "CLAUDE.md"
                codex.write_text(template)
                claude.write_text("Existing Claude guidance")
                with self.assertRaises(ValueError):
                    RENDER(sources, codex, claude)
                self.assertEqual(codex.read_text(), template)
                self.assertEqual(claude.read_text(), "Existing Claude guidance")

    def test_image_sources_are_complete_for_all_agents(self) -> None:
        sources = IMAGE / "agent-instructions"
        paths = sorted(sources.glob("*.md"))
        self.assertTrue(paths)
        opencode = json.loads((IMAGE / "opencode.json").read_text())
        self.assertEqual(opencode["instructions"],
                         [f"/etc/exoshell/instructions/{path.name}" for path in paths])
        expected = "\n\n".join(path.read_text().rstrip("\n") for path in paths) + "\n"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            codex = directory / "config.toml"
            claude = directory / "claude-code/CLAUDE.md"
            codex.write_text((IMAGE / "codex.config.toml").read_text())
            result = subprocess.run(
                [sys.executable, str(HELPER), "--instructions-dir", str(sources),
                 "--codex-config", str(codex), "--claude-memory", str(claude)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(tomllib.loads(codex.read_text())["developer_instructions"], expected)
            self.assertEqual(claude.read_text(), expected)


if __name__ == "__main__":
    unittest.main()
