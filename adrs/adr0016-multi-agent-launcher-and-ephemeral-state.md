---
status: accepted
date: 2026-09-20
author: Tomas Mlcoch
topics:
  - launcher
  - agent-state
---

# 16. Multi-agent Launcher and Ephemeral State

## Context

The image contains Codex, Claude Code, and OpenCode, but the launcher and state
mount supported only Codex. Sharing a persistent home would retain histories
and could also retain API credentials written by agent login flows. OpenCode
supports multiple inference backends whose credentials and endpoints should
remain independently selectable.

## Decision

We will use one generic launcher with explicit agent selection. Common
providers will compose with a selected agent's provider list, while CLI
provider options replace that full composition.

We will mount only the selected agent's user state as tmpfs. Non-secret pinned
defaults will remain image-managed. Credentials will come from backend-specific
Providers v2 profiles; OpenCode authentication commands that write `auth.json`
will not be used.

## Consequences

- Agent histories, onboarding state, and user-level choices are discarded with
  each sandbox, while project configuration under `/workspace` persists.
- Claude subscription OAuth is unsupported; Claude uses an Anthropic API key.
- OpenCode stays backend-neutral and can use separate OpenAI, Anthropic, or
  OpenRouter profiles.
- Provider profiles exporting the same environment variable must not be
  attached together.
- Adding another agent requires an executable, state layout, policy paths, and
  provider binary coverage, but no additional launcher wrapper.

## References

- [Generic launcher](../run-exoshell-agent.sh)
- [Launcher implementation](../scripts/exoshell_agent.py)
- [Provider setup](../providers.md)
- [OpenCode providers](https://opencode.ai/docs/providers)
- [OpenCode managed configuration](https://opencode.ai/docs/config/#managed-settings)
