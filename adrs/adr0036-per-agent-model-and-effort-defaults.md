---
status: accepted
date: 2026-10-07
topics:
  - launcher
  - agent-state
---

# 36. Per-agent Model and Effort Defaults

## Context

Disposable sandboxes discard user-level model selections. Selecting a starting
model and effort previously required native arguments or an image rebuild.
The launcher already has per-agent provider configuration, but clients use
different effort interfaces. In particular, OpenCode 1.18.34 supports
`run --variant` while its full-screen interactive CLI requires an agent's
configured model and variant pair.

## Decision

We will accept optional `model` and `effort` strings in each agent table and
provide launcher overrides and clearing options. Native forwarded selections
will take precedence, and native agents will validate supported model IDs and
effort values. Unspecified fields will retain native defaults.

We will use Codex's repeatable CLI configuration overrides and Claude's native
model and effort options. OpenCode interactive effort will require an explicit
model and merge the pair into the built-in build and plan agents through
disposable inline configuration in the image startup helper. OpenCode run
will use its native variant option. Custom agents will retain their own
variant configuration.

## Consequences

- Local selections no longer require changing image-managed defaults.
- Effort has a consistent field name but agent- and model-specific meaning.
- Clearing a launcher selection suppresses ExOShell's value without resetting
  native configuration.
- Interactive OpenCode effort requires rebuilding dependent images to install
  the updated startup helper; unrelated config and provider-controlled MCP
  enablement are preserved.
- No project configuration files or credentials are written by this feature.

## References

- [Multi-agent launcher and ephemeral state](adr0016-multi-agent-launcher-and-ephemeral-state.md)
- [Codex configuration reference](https://developers.openai.com/codex/config-reference/)
- [Claude CLI reference](https://code.claude.com/docs/en/cli-reference)
- [OpenCode CLI reference](https://opencode.ai/docs/cli/)
- [OpenCode agent configuration](https://opencode.ai/docs/agents/)
