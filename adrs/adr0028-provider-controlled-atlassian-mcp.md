---
status: accepted
date: 2026-10-03
topics:
  - providers
  - sandbox-image
  - atlassian
---

# 28. Enable Atlassian MCP from its provider credential at agent startup

## Context

The image registers Atlassian MCP unconditionally in Codex, Claude Code, and
OpenCode, even without an attached credential provider. This creates connection
failures and exposes an integration that some users do not need. Provider
instance names are user-selected, so matching a launcher provider name is not
a reliable activation signal.

OpenShell supplies provider credential placeholders to workload processes.
Runtime provider changes affect new process environments; existing processes
retain their original environment. The existing image helper already runs
before the selected agent, but ADR-0023 excludes provider-inferred integrations.

Client wrappers would cover bare invocations but introduce another launch path.
Host-side provider inspection would add gateway dependencies and still require
client configuration. A small addition to the existing image helper can use
the credential environment already supplied by OpenShell.

## Decision

We will disable Atlassian MCP in fresh images and enable the built-in
`atlassian` entry in `exoshell-agent` only when `ATLASSIAN_MCP_BEARER_TOKEN` is
non-empty. This is a narrow exception to ADR-0023's explicit-opt-in rule.
GWS will continue to require its existing explicit opt-in.

The helper will set Codex's final command-line enablement override, merge
OpenCode's inline runtime enablement override, and atomically update Claude's
user MCP entries and current-project disabled-server list. Attachment state
will control startup enablement even when existing configuration disagrees.
Unrelated settings, MCP entries, and command arguments will be preserved.

Claude's image will set `CLAUDE_CONFIG_DIR=/sandbox/.claude` so its user state
can be atomically updated within the existing writable filesystem policy.
Its Atlassian definition will remain a non-secret image template containing
environment references. No credential value will be written to configuration.

## Consequences

- Users without the provider do not connect to Atlassian at startup.
- Arbitrarily named provider instances work through the shared environment key.
- Bare client commands bypass recomputation; the launcher and direct users of
  `exoshell-agent` receive automatic behavior. Claude's generated state remains
  until another helper invocation or sandbox deletion.
- Provider changes require waiting for application and launching the helper
  through a fresh exec or SSH environment. Restarting from an old shell is
  insufficient. This does not implement live agent reconfiguration.
- Placeholder presence does not establish token validity or freshness. OAuth
  refresh remains host-side as described in ADR-0017.
- Client managed restrictions remain effective. This configuration choice is
  not an authorization boundary; OpenShell and upstream credential scope
  continue to enforce access.
- Base and derived images must be rebuilt. Existing provider profiles need an
  update to include Codex and Claude executable permissions.

## References

- [Image startup decision](adr0023-agent-neutral-image-startup.md)
- [OAuth credential decision](adr0017-atlassian-mcp-oauth-bearer.md)
- [Image helper](../sandboxes/exoshell-base/exoshell-agent)
- [OpenShell provider lifecycle and environment limitations](https://docs.nvidia.com/openshell/how-it-works/providers/profiles#runtime-limitations)
- [Codex MCP enablement](https://developers.openai.com/codex/config-reference/)
- [OpenCode inline configuration precedence](https://opencode.ai/docs/config/#precedence-order)
- [Claude per-project MCP controls](https://code.claude.com/docs/en/mcp#disable-a-server-without-removing-it)
- [Claude configuration directory](https://code.claude.com/docs/en/settings#find-or-create-your-settings-files)
