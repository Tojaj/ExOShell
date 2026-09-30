---
status: accepted
date: 2026-09-18
author: Tomas Mlcoch
topics:
  - sandbox-image
  - codex
---

# 13. Install non-secret Codex defaults as system configuration

## Context

The launcher previously discovered an optional host `config.toml`, mounted it
read-only, and copied it into the writable tmpfs at `CODEX_HOME` before
starting Codex. That made normal image defaults dependent on launcher logic and
left them invisible whenever no host configuration was selected.

Codex loads `/etc/codex/config.toml` as its Unix system configuration. It has
lower precedence than CLI overrides, trusted project configuration, selected
profiles, user configuration, and cloud-managed defaults. This lets an image
provide shared defaults while allowing narrower scopes to override them.

## Decision

We will keep the editable non-secret Codex configuration beside the base image
Dockerfile as `codex.config.toml` and copy it to `/etc/codex/config.toml` at
build time. It will set the model, reasoning effort, sandbox mode, approval
policy, API-key authentication preference, and TUI status line.

The primary Codex launcher will rely on this system configuration and will not
discover, stage, mount, or copy a host Codex configuration. `CODEX_HOME` will
remain a writable tmpfs for runtime state.

## Consequences

- The image must be rebuilt for a system-default change.
- The system file must contain no credentials, private service details, or
  machine-specific values.
- Users can override these defaults through higher-precedence Codex
  configuration or command-line settings.
- The pinned Codex version must be smoke-tested when either its version or the
  system configuration keys change.

## References

- [Base image configuration](../sandboxes/exoshell-base/codex.config.toml)
- [Base image Dockerfile](../sandboxes/exoshell-base/Dockerfile)
- [OpenAI Codex configuration basics](https://developers.openai.com/codex/config-basic)
