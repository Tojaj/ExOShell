---
status: accepted
date: 2026-11-23
topics:
  - sandbox-image
  - launcher
---

# 47. Load personal agent instructions at sandbox startup

## Context

The image supplies operational guidance for every project. Users also have
personal instructions that change between launches. Rebuilding an image for
each edit is expensive, and editing a project's instructions changes the
checkout for other contributors. Users may already keep guidance in files or
want to supply just one sentence. Inferring which they meant from a string
would turn a misspelled file path into literal prompt text.

## Decision

We will accept path lists and optional literal text through separate TOML
settings. We will expand directories in filename order and append configured
text after all paths. Either CLI input flag will replace the complete configured
selection, preserving the order of mixed CLI flags.

We will reuse the local Podman snapshot approach from ADR-0038. The launcher
will mount a private combined UTF-8 file read-only for startup. The image will
add its contents to Codex's active global AGENTS file, Claude Code's personal
CLAUDE.md, or OpenCode's global AGENTS.md, according to the selected agent.
This lets each client combine personal guidance with image and project guidance
using its native discovery and precedence rules.

## Consequences

- A launch sees a stable copy of the selected guidance. Kept sandboxes retain
  the imported copy after host snapshot cleanup.
- Image maintainers must rebuild for instruction import support. Custom policies
  must allow reading the snapshot in /tmp and writing the agent's user config.
- Verbose output can report paths and inline text presence. Literal CLI
  arguments are still visible to the invoking shell and host process tools.

## References

- [Shared image guidance](adr0032-shared-image-agent-instructions.md)
- [User skill snapshots](adr0038-user-skill-snapshots.md)
- [Codex global instructions](https://developers.openai.com/codex/guides/agents-md/)
- [Claude Code personal memory](https://code.claude.com/docs/en/memory)
- [OpenCode global instructions](https://opencode.ai/docs/instructions/)
