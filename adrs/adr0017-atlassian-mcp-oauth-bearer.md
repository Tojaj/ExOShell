---
status: accepted
date: 2026-09-21
author: Tomas Mlcoch
topics:
  - providers
  - credentials
  - atlassian
  - oauth
---

# 17. Atlassian Rovo MCP: OAuth 2.1 bearer token via provider

## Context

An initial Atlassian Rovo MCP integration used an API token with Basic
authentication, injected through an OpenShell provider as a header placeholder.
This approach depends on the site enabling API token authentication for the
account; it cannot serve sites where that authentication method is unavailable.

The Atlassian MCP server supports OAuth 2.1 natively via the MCP specification's
standard remote-server OAuth mechanism. Discovery from
`mcp.atlassian.com/.well-known/oauth-authorization-server` shows:

- Authorization: `https://mcp.atlassian.com/v1/authorize`
- Token exchange / refresh / revocation: `https://mcp.atlassian.com/v1/token`
- Dynamic client registration: `https://mcp.atlassian.com/v1/register`
- Public client flow supported (`"none"` in `token_endpoint_auth_methods_supported`)
- PKCE with S256

Three approaches were considered:

**Option A — Bearer token via provider (same architecture as Basic Auth).**
Perform the OAuth flow on the host, obtain a short-lived access token, and
inject it as a Bearer credential through the existing provider profile. The
provider replaces the header placeholder; the agent never sees the real token.
Simple and reuses the existing architecture. Downside: access tokens expire in
~1 hour and cannot self-renew inside the sandbox.

**Option B — Request body rewrite (gws-oauth pattern, ADR 0002).** Inject
`client_id` and `refresh_token` as provider placeholders, use
`request_body_credential_rewrite` on the `/v1/token` endpoint so the proxy
substitutes real values during token refresh. Would enable self-renewal. However,
Atlassian OAuth 2.1 rotates refresh tokens: each refresh returns a new one,
invalidating the old. After one refresh cycle the real (rotated) refresh token
replaces the placeholder in OpenCode's auth state, and subsequent refresh
requests bypass the proxy rewrite. The body-rewrite pattern is incompatible
with rotating refresh tokens.

**Option C — Native OpenCode OAuth inside the sandbox.** Set `"oauth": true` in
the OpenCode MCP config and let it handle the full OAuth flow internally. The
initial authorization requires a browser, which is not available in the sandbox.
OpenShell's built-in port forwarding (`openshell forward service`) can bridge
the OAuth callback port from the host into the sandbox's loopback interface,
enabling the browser redirect to reach OpenCode. This enables self-sustaining
sessions but places refresh tokens in the sandbox, readable by the agent.

## Decision

We will use Option A (bearer token via provider) as the immediate solution.
Option C is the intended long-term approach and is documented below for future
implementation.

The provider profile changes from `auth_style: basic` to `auth_style: bearer`.
A host-side helper script (`scripts/atlassian-mcp-oauth.sh`) handles the OAuth
2.1 authorization code flow with PKCE, dynamic client registration, and token
refresh. The script persists the `client_id` and `refresh_token` on the host;
only the short-lived access token enters the provider credential store.

## Consequences

**Positive:**
- The access token (the only credential that enters the sandbox) is short-lived
  (~1 hour). Even if read by the agent, its utility window is narrow.
- No long-lived secrets (refresh token, client credentials) in the sandbox.
- Minimal change from the existing Basic Auth architecture — same provider
  pattern and agent MCP configuration structure.
- OAuth is standard and doesn't require admin to enable API token auth.

**Negative / constraints:**
- Access token expires after ~1 hour. Refreshing requires running the host-side
  script and recreating the provider instance. If provider credentials cannot be
  hot-reloaded for a running sandbox, this requires sandbox restart.
- The host-side script must be re-run before each session (or a cron job must
  keep the token fresh).
- Dynamic client registration may assign a new `client_id` if the registration
  endpoint does not persist registrations across calls. The script reuses a
  stored `client_id` when available.

## Future: Option C (native OAuth with port forwarding)

When the limitations of Option A become too disruptive, switch to Option C:

1. Set `"oauth": true` in OpenCode's MCP config, remove custom `headers`.
2. Remove or minimize the `atlassian-mcp` provider (no credential injection
   needed; provider may be retained for binary restriction if supported).
3. At sandbox startup (or on first OAuth challenge), use OpenShell port
   forwarding to bridge the callback:
   ```
   openshell forward service <sandbox> --target-port <PORT> --local <PORT>
   ```
4. User opens the auth URL in the host browser; the callback reaches OpenCode
   through the forwarded port.
5. OpenCode stores tokens in its auth state and handles refresh autonomously.

Security trade-off: refresh tokens and access tokens become visible in the
sandbox (stored in OpenCode's `auth.json`). Mitigated by: refresh token
rotation limits leaked-token utility, and 90-day inactivity expiry.

## References

- [`scripts/atlassian-mcp-oauth.sh`](../scripts/atlassian-mcp-oauth.sh) — host-side OAuth helper
- [`provider-profiles/provider-atlassian-mcp.yaml`](../provider-profiles/provider-atlassian-mcp.yaml) — provider profile
- [ADR 2](adr0002-gws-credentials-via-provider-body-rewrite.md) — gws body rewrite (not applicable here due to refresh token rotation)
- [SPEC.md §1](../SPEC.md) — security goals
- [Atlassian MCP OAuth metadata](https://mcp.atlassian.com/.well-known/oauth-authorization-server) — discovery endpoint
- [Atlassian OAuth 2.1 guide](https://developer.atlassian.com/cloud/rovo-mcp/guides/configuring-oauth-2-1/)
