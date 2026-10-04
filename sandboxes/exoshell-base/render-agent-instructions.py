#!/usr/bin/env python3
"""Render shared Markdown instructions into image-level agent configuration."""

import argparse
import json
from pathlib import Path
import tomllib


def render(instructions_dir: Path, codex_config: Path, claude_memory: Path) -> None:
    template = codex_config.read_text(encoding="utf-8")
    if "developer_instructions" in tomllib.loads(template):
        raise ValueError("Codex template already defines developer_instructions; install a fresh template")

    sources = sorted(instructions_dir.glob("*.md"))
    if not sources:
        raise ValueError(f"No Markdown instructions found in {instructions_dir}")
    content = "\n\n".join(path.read_text(encoding="utf-8").rstrip("\n") for path in sources) + "\n"
    # JSON's basic string escapes are also TOML escapes. Keep Unicode literal
    # to avoid surrogate pairs, and escape DEL, which TOML prohibits literally.
    value = json.dumps(content, ensure_ascii=False).replace("\x7f", "\\u007f")
    rendered = f"developer_instructions = {value}\n\n{template}"
    tomllib.loads(rendered)

    claude_memory.parent.mkdir(parents=True, exist_ok=True)
    codex_config.write_text(rendered, encoding="utf-8")
    claude_memory.write_text(content, encoding="utf-8")
    codex_config.chmod(0o644)
    claude_memory.chmod(0o644)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instructions-dir", type=Path, default=Path("/etc/exoshell/instructions"))
    parser.add_argument("--codex-config", type=Path, default=Path("/etc/codex/config.toml"))
    parser.add_argument("--claude-memory", type=Path, default=Path("/etc/claude-code/CLAUDE.md"))
    args = parser.parse_args()
    try:
        render(args.instructions_dir, args.codex_config, args.claude_memory)
    except (OSError, ValueError) as error:
        parser.exit(1, f"render-agent-instructions: {error}\n")


if __name__ == "__main__":
    main()
