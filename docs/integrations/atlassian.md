# Atlassian Rovo MCP

*Run these commands on the gateway host, from your ExOShell checkout: the paths
are relative to it. Blocks marked as sandbox commands run inside a sandbox.*

`exoshell-atlassian-mcp` supplies a short-lived OAuth 2.1 Bearer token to the Atlassian
Rovo MCP endpoint used by the image-provided Codex, Claude Code, and OpenCode
configurations. The refresh token remains on the host.

## Set up the provider

```bash
openshell provider profile lint -f provider-profiles/provider-atlassian-mcp.yaml
openshell provider profile import -f provider-profiles/provider-atlassian-mcp.yaml
```

```bash
./scripts/atlassian-mcp-oauth.sh sync
```

`sync` creates `exoshell-atlassian-mcp` from the imported profile when needed, opens a
browser for authorization when host-side OAuth state is unavailable, and
otherwise refreshes the provider directly. It stores per-provider client and
refresh-token state in `~/.config/openshell/atlassian-mcp-oauth.json`, never the
access token. Use `--provider <name>` to manage a separately named instance.
To revoke access and remove the default instance:

```bash
./scripts/atlassian-mcp-oauth.sh revoke --provider exoshell-atlassian-mcp
openshell provider delete exoshell-atlassian-mcp
```

## Use it in a session

Attach this provider only to Codex, Claude Code, or OpenCode sandboxes.
Synchronize it before starting a new sandbox or agent process because access
tokens expire in about one hour. Restart the agent after changing its
configuration because MCP configuration is loaded only at startup.
After attaching, detaching, or updating a provider on an existing sandbox, wait
for OpenShell to apply the change, then invoke the helper in a fresh OpenShell
exec or SSH session. An already-running shell retains its old credential
environment. A non-empty placeholder does not establish token validity.

Smoke tests in a newly started sandbox:

```bash
# inside the sandbox
# Codex
exoshell-agent "$PWD" -- codex mcp list

# Claude Code
exoshell-agent "$PWD" -- claude mcp list

# OpenCode
exoshell-agent "$PWD" -- opencode mcp list
```

OpenCode v2 serves CLI requests from a per-user background server inside the
sandbox; a first `mcp list` can report no servers while it is still starting,
so query again before concluding a server is missing. With a synchronized
provider attached, confirm that Atlassian is enabled, then make a read-only MCP
request through the selected agent. Repeat without the provider: Codex and
OpenCode should show it disabled; Claude should omit its image-provided entry.
A project-defined Claude entry with the same name is disabled for that project
instead. No Atlassian request should be attempted.

## How it works

Atlassian MCP is disabled in fresh images. The launcher's `exoshell-agent`
startup helper enables it only when `ATLASSIAN_MCP_BEARER_TOKEN` is non-empty
in the agent's environment. OpenShell supplies an opaque credential placeholder
when the provider is attached; the helper does not inspect or persist the token.
Provider instance names are arbitrary: a separately named instance using the
same credential environment key works too. Missing or empty credentials disable
the integration without an Atlassian connection attempt.

The helper controls the built-in `atlassian` entry at each startup, overriding
conflicting enable/disable settings. Other MCP servers and agent settings are
preserved. Codex uses a command-line override, OpenCode merges an inline runtime
override, and Claude updates its private user configuration and per-project
disabled-server list. Claude state lives in `/sandbox/.claude/.claude.json`
through `CLAUDE_CONFIG_DIR`, within the existing writable filesystem policy.
Bare client invocations bypass this startup decision; use the launcher or
`exoshell-agent` for automatic behavior. Client managed policy and explicit
configuration-source restrictions still apply; this is startup configuration,
not a security boundary.

The provider uses a Bearer token instead of request-body rewriting because
Atlassian rotates refresh tokens. See [ADR 17](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0017-atlassian-mcp-oauth-bearer.md).
