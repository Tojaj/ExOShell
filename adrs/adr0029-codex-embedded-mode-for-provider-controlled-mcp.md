---
status: accepted
date: 2026-10-03
topics:
  - codex
  - providers
  - sandbox-lifecycle
---

# 29. Accept Codex embedded mode for provider-controlled MCP startup

## Context

Commit `8baf7f4430e8b45b5e0256580da12d1da97ece13` implements ADR-0028 by
adding `--config mcp_servers.atlassian.enabled=true|false` to every Codex
invocation through `exoshell-agent`. The override is also added when the
Atlassian provider is absent, so conflicting configuration cannot enable the
entry through this startup path.

Codex 0.160.0 reports the following warning for interactive startup:

```text
Running without the shared background server: command-line configuration overrides (-c, --enable, --disable, or --search) requires embedded mode.
```

The session continues with its own backend instead of joining the shared
background server. Atlassian MCP was confirmed working in this mode. Embedded
mode does not inherently disable MCP, ordinary coding, or subagents. Codex
also provides `--no-daemon` as an explicit way to bypass the shared server.

The normal ExOShell launcher passes `--no-keep`: OpenShell deletes the sandbox
after the canonical agent process exits. Agent state and any background server
inside that sandbox are discarded. The normal flow does not require a shared
server or continuation after CLI exit, although a shared server could serve
multiple clients during a sandbox's lifetime.

The alternatives evaluated were:

- Retain the CLI override. Provider attachment controls entry enablement without
  rewriting user configuration, at the cost of embedded mode.
- Atomically update only `mcp_servers.atlassian.enabled` in user configuration.
  This avoids the injected CLI override, but mutates user state and allows
  higher-priority project, profile, and CLI settings to override the result.
  It changes ADR-0028's guarantee that attachment state controls enablement.
- Run `codex mcp add/remove` before starting Codex. In an isolated temporary
  `CODEX_HOME` with Codex 0.160.0, `add` replaced the named server definition,
  dropping its existing tool allowlist and timeout, and copied inherited MCP
  entries into the user file. It omitted `enabled`, leaving the image's
  system-level `enabled = false` effective. Removing the user entry likewise
  left the system definition available. Add/remove is therefore not a suitable
  enable/disable switch for the current image defaults.

## Decision

We will retain ADR-0028's final CLI enablement override and accept Codex's
embedded-mode warning in the normal disposable sandbox workflow. This keeps
provider-controlled enablement predictable, preserves user configuration
files, and starts Codex with the fresh process's credential environment.

We will not rewrite user configuration or add `--no-daemon` solely to eliminate
the warning. This decision supplements ADR-0028 without superseding it.

## Consequences

- These interactive sessions do not participate in shared-daemon session
  management, such as browsing them through `codex agents`. The normal
  `--no-keep` flow does not depend on those capabilities.
- The warning describes the selected execution mode, not an Atlassian
  connection failure. It does not change OpenShell authorization or upstream
  credential scope.
- `--keep` retains the sandbox for diagnosis; it does not make this launch path
  use the shared server or guarantee that active work survives CLI exit.
- Provider changes still require a fresh process environment. If a shared
  daemon is adopted later, verify how it receives changed credential
  environments rather than assuming configuration-file updates refresh them.
- Revisit this decision if ExOShell adopts persistent or multiple-client
  sessions, or if upstream Codex changes override compatibility. The observed
  warning and `mcp add/remove` behavior above are specific to version 0.160.0.

## References

- [Provider-controlled Atlassian MCP startup](adr0028-provider-controlled-atlassian-mcp.md)
- [Ephemeral sandbox lifecycle](adr0018-ephemeral-labeled-sandboxes.md)
- [Agent state cleanup](adr0019-sandbox-lifecycle-for-agent-state.md)
- [Image startup helper](../sandboxes/exoshell-base/exoshell-agent)
- [OpenShell sandbox management](https://docs.nvidia.com/openshell/sandboxes/manage-sandboxes)
- [Codex configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic#configuration-precedence)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
- [Codex changelog: automatic background-server startup and daemon bypass](https://learn.chatgpt.com/docs/changelog)
