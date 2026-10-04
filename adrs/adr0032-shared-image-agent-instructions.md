---
status: accepted
date: 2026-10-04
topics:
  - sandbox-image
  - codex
  - claude-code
  - opencode
---

# 32. Share image instructions across coding agents

## Context

[ADR-0022](adr0022-opencode-image-instructions.md) introduced image-provided
operational instructions for OpenCode. The guidance covers OpenShell policy,
SELinux bind-mount labels, and search tools, and applies equally to Codex and
Claude Code. Separate copies would drift as operational knowledge changes.
Codex already loads image defaults from system configuration under ADR-0013.

The alternatives considered were:

- Generate Codex's additional `developer_instructions` in system configuration
  and Claude's managed `CLAUDE.md` during the image build. Both load without
  depending on mutable user configuration or the startup helper.
- Install Codex's global `AGENTS.md`. It follows the project instruction
  hierarchy, but depends on `CODEX_HOME` and can be bypassed by
  `AGENTS.override.md`.
- Inject instructions through `exoshell-agent`. This adds runtime argument
  handling and does not cover direct agent launches.
- Package the guidance as a shared skill. Selective activation may leave the
  agent without the guidance when it encounters an operational failure.

Codex's `model_instructions_file` replaces its built-in instructions rather
than adding this guidance. It is unsuitable for the intended extension.

## Decision

We will supersede ADR-0022 with one set of small, agent-neutral Markdown files
in the base image's `agent-instructions/`, installed root-owned and readable
under `/etc/exoshell/instructions/`.

We will combine all top-level Markdown files in filename order at image build
time. The build helper will prepend the content as the top-level
`developer_instructions` value in `/etc/codex/config.toml`, preserving the
other template settings, and write identical content to Claude Code's managed
`/etc/claude-code/CLAUDE.md`. It will reject a Codex template that already
defines `developer_instructions`. OpenCode will explicitly list the individual
installed instruction files in its global configuration.

We will retain the helper in the image so derived images can install additional
guidance, copy a fresh Codex template, and regenerate both agents' content at
build time. We will keep organization-specific instructions in separate
customization repositories.

## Consequences

- The agents share maintained sources; generated content is not committed.
- Direct agent launches receive the guidance independently of `CODEX_HOME`
  and `CLAUDE_CONFIG_DIR`, without launcher changes or added runtime flags.
- Codex receives developer-level instructions, which take priority over
  project guidance. Higher-precedence configuration can replace the entire
  `developer_instructions` value rather than appending to it.
- Claude's managed memory cannot be excluded through `claudeMdExcludes`.
  It remains behavioral guidance, not a technical enforcement mechanism.
- Adding or editing guidance requires rebuilding the base and derived images.
  New files must also be added to OpenCode's explicit instruction list.
- Derived images must regenerate after source changes and provide a fresh
  Codex template to avoid duplicating or silently replacing instructions.
- Tests must cover TOML escaping, preservation of configuration, identical
  generated content, and OpenCode's coverage of the installed files.

## References

- [Original OpenCode instruction decision](adr0022-opencode-image-instructions.md)
- [System Codex configuration](adr0013-system-codex-configuration.md)
- [Shared instruction sources](../sandboxes/exoshell-base/agent-instructions/)
- [Build helper](../sandboxes/exoshell-base/render-agent-instructions.py)
- [Base image Dockerfile](../sandboxes/exoshell-base/Dockerfile)
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Codex global and project instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Claude Code managed memory](https://code.claude.com/docs/en/memory)
- [OpenCode configuration instructions](https://opencode.ai/docs/config/#instructions)
