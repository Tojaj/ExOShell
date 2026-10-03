---
status: accepted
date: 2026-10-03
topics:
  - providers
  - launcher
  - sandbox-image
  - gws
  - atlassian
---

# 30. Initialize agent integrations from provider credentials

## Context

[ADR-0023](adr0023-agent-neutral-image-startup.md) put shared startup in an
image executable but required explicit integration opt-in.
[ADR-0028](adr0028-provider-controlled-atlassian-mcp.md) enabled Atlassian MCP
from its provider credential while retaining a separate GWS switch. Attaching
a GWS provider and enabling GWS initialization express the same intent twice.
The GWS switch also provisions runtime storage, so removing it requires a
storage decision independent of credential availability.

Conditional mounting based on provider instance names would couple the launcher
to user-selected names. Host-side inspection would add gateway dependencies.
Creating an ordinary writable directory in the helper would work, but retain
GWS files in the container layer with `--keep`. An unconditional tmpfs preserves
the current storage behavior and supports providers attached after creation.

## Decision

We will preserve `/usr/local/bin/exoshell-agent PROJECT -- COMMAND [ARG ...]`:
validate an absolute project directory below `/workspace`, initialize supported
integrations, change directory, and replace the helper with the selected command.
The launcher will continue selecting the agent, providers, policy, mounts, Git
identity, and project mapping. Integration activation will use non-empty
credential environment values rather than provider instance names.

We will initialize GWS when `GWS_CLIENT_ID`, `GWS_CLIENT_SECRET`, and
`GWS_REFRESH_TOKEN` are all non-empty. No non-empty values means skip GWS;
a partial set means fail before starting the command, naming only missing keys.
The helper will preserve atomic private `authorized_user` JSON creation,
private config storage, and child-process GWS path variables from ADR-0002.
The launcher will always mount `/tmp/gws` as tmpfs, while direct OpenShell
users will supply a writable directory there, preferably through tmpfs.
We will remove TOML `gws`, CLI `--gws`/`--no-gws`, and `EXOSHELL_GWS` activation.

We will preserve ADR-0028's Atlassian behavior: fresh images disable the built-in
entry, and the helper enables it only with non-empty `ATLASSIAN_MCP_BEARER_TOKEN`.
Codex receives a final command-line enablement override, OpenCode receives a
merged inline override, and Claude receives atomic user and current-project
MCP state updates with a non-secret environment-referencing template.
Unrelated settings and arguments remain intact. Claude user state stays under
`CLAUDE_CONFIG_DIR=/sandbox/.claude`. ADR-0029's Codex embedded-mode tradeoff
continues to apply.

## Consequences

- Attaching the appropriate provider is the only opt-in needed for initialization.
  No provider-profile change is required for GWS.
- Launches without GWS credentials perform no GWS file or environment changes.
  Every launcher-created sandbox nevertheless has GWS tmpfs storage available.
- Existing local TOML files and scripts must remove the old GWS options; they
  are rejected by the launcher's ordinary unknown-key and argument validation.
  Base and derived images must be rebuilt to receive the new helper.
- Provider changes require waiting for application and launching the helper
  through a fresh exec or SSH environment. Existing shells and agents retain
  their environment; bare client commands bypass startup recomputation.
- Placeholder availability does not prove validity or freshness. Initialization
  is not an authorization boundary and does not revoke already obtained Google
  access tokens or erase existing GWS files after provider detachment.
- Existing GWS credential rewriting and Atlassian host-side OAuth management
  remain unchanged. Client managed restrictions remain effective.

## References

- [Image helper](../sandboxes/exoshell-base/exoshell-agent)
- [Launcher](../scripts/exoshell_agent.py)
- [GWS credential rewriting](adr0002-gws-credentials-via-provider-body-rewrite.md)
- [Atlassian OAuth management](adr0017-atlassian-mcp-oauth-bearer.md)
- [Codex embedded mode](adr0029-codex-embedded-mode-for-provider-controlled-mcp.md)
- [OpenShell provider credential environment](https://docs.nvidia.com/openshell/how-it-works/providers/profiles#profile-sections)
- [OpenShell provider runtime limitations](https://docs.nvidia.com/openshell/how-it-works/providers/profiles#runtime-limitations)
