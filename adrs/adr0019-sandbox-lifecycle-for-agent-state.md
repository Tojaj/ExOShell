---
status: accepted
date: 2026-09-24
author: Tomas Mlcoch
topics:
  - sandbox-lifecycle
  - agent-state
---

# 19. Use sandbox lifecycle for agent state cleanup

## Context

The launcher mounted each selected agent's user-state directories as tmpfs to
discard histories, settings, and credentials after use. The normal launcher
lifecycle now passes `--no-keep`, which deletes the sandbox after its agent
exits, including after a nonzero exit. The tmpfs mounts therefore duplicate the
normal cleanup mechanism and hide image-provided user-path configuration.

Retained sandboxes are explicitly requested through `--keep` for diagnosis.
Hiding agent state from those sandboxes prevents investigation of configuration,
cache, history, and login failures.

## Decision

We will leave Codex, Claude Code, and OpenCode state in the sandbox container
layer. The launcher will not mount per-agent state directories as tmpfs or set
environment variables that only redirect them to those directories. We will
continue mounting GWS credentials on tmpfs because that directory is generated
from provider-backed credentials independently of the agent lifecycle.

The generic image will provide OpenCode defaults at the standard global path.
A derived image can add its own custom configuration file through
`OPENCODE_CONFIG`. Project configuration will load after both image layers and
can override their defaults. This provides a reusable layering pattern for
site-specific or user-specific sandbox images without modifying the generic
base image.

## Consequences

- Default `--no-keep` sandboxes still discard all agent state on deletion.
- A `--keep` sandbox can be inspected with the state that caused a failure.
- Retained sandboxes can contain credentials written by interactive login flows
  and must be deleted after investigation.
- Image-provided OpenCode global and derived-image custom configuration are
  visible and merge before project configuration.
- This decision replaces the per-agent tmpfs state-mount portion of
  [ADR-0016](adr0016-multi-agent-launcher-and-ephemeral-state.md).

## References

- [Launcher implementation](../scripts/exoshell_agent.py)
- [Derived image configuration](../CUSTOMIZATION.md#create-a-custom-image)
- [OpenCode configuration](https://opencode.ai/docs/config/)
