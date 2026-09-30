---
status: accepted
date: 2026-09-11
author: Tomas Mlcoch
topics:
  - providers
  - credentials
  - gws
---

# 2. Hide gws OAuth credentials using a provider with request body rewrite

## Context

The gws CLI (Google Workspace) requires three secrets for its OAuth2 flow:
`client_id`, `client_secret`, and `refresh_token`. It POSTs all three to
an OAuth token endpoint and receives a short-lived access token. With GWS
0.22.5, `yup-oauth2` uses `accounts.google.com/o/oauth2/token` by default;
GWS's proxy-aware refresh path uses `oauth2.googleapis.com/token`.

The initial setup bind-mounted the host `~/.config/gws` directory (read-only)
into the sandbox. This worked because gws decrypts `credentials.enc` using the
host keyring, which was accessible via the mount. The downside: the agent
process can read the client_secret and refresh_token — both are long-lived and
grant full Workspace access for the authorized scopes.

Three approaches were considered:

**Option A — bind mount (status quo).** Mount `~/.config/gws` read-only. The
agent can read the decrypted credentials in memory once gws loads them. Simple
and working, but violates the project's security goal of hiding secrets from
the agent where feasible (SPEC.md §1, goal 2).

**Option B — OpenShell Provider with `request_body_credential_rewrite`.** Create
a provider profile that injects `client_id`, `client_secret`, and
`refresh_token` as placeholder env vars. A credentials file inside the sandbox
contains placeholder strings (`openshell:resolve:env:KEY`). When gws POSTs
these to the token endpoint, the proxy substitutes real values in the request
body before it reaches Google. The agent never sees the real secrets. The
access token (returned by Google) is short-lived (~1 hour) and held only in
the gws process memory.

**Option C — pre-obtained access token via `GOOGLE_WORKSPACE_CLI_TOKEN`.**
Generate a short-lived access token on the host and inject it as a provider
credential. No token exchange needed. Simple, but access tokens expire in ~1
hour with no self-renewal — the agent would lose Workspace access mid-session.

A key constraint: googleworkspace/cli#857 means that when `credentials.enc`
exists in the gws config directory, all env-var auth sources are silently
ignored. Option B requires not mounting `~/.config/gws` (so `credentials.enc`
is absent) and instead pointing `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` to a
separate writable directory.

Verified experimentally: a credentials file containing placeholder values
(with `"type": "authorized_user"`) passes gws parsing and reaches the HTTP
request — gws does not validate credential format locally.

## Decision

We will use Option B: a custom provider profile (`gws-oauth`) with
`request_body_credential_rewrite: true` on both token endpoints. The
`accounts.google.com` endpoint is limited to `/o/oauth2/token`, which takes
precedence over the audit wildcard for other `google.com` paths. The three
OAuth credentials are injected as provider-managed placeholders and never
enter the sandbox in readable form.

The `~/.config/gws` bind mount is removed. A writable tmpfs replaces it for
gws runtime state (token cache, discovery cache). A placeholder credentials
file is written at sandbox startup.

## Consequences

**Positive:**
- `client_secret` and `refresh_token` are never readable by the agent
  process. Only the short-lived access token (~1h) exists in process memory.
- Token refresh works transparently — gws re-reads the placeholder
  credentials file and the proxy rewrites each token exchange request.
- Aligns with SPEC.md goal 2: "API keys / tokens the agent uses are not
  readable by the agent where feasible."

**Negative / constraints:**
- Depends on OpenShell's `request_body_credential_rewrite` correctly handling
  placeholder substitution in form-urlencoded or JSON request bodies. If gws
  URL-encodes the `:` in placeholder strings as `%3A`, the proxy must decode
  before matching.
- `gws auth status` in the sandbox will show placeholder strings for
  `client_id` instead of the real value. Cosmetic only.
- Blocked by googleworkspace/cli#857 if `credentials.enc` is present. Must
  not mount `~/.config/gws`. If the bug is fixed upstream (env vars take
  proper precedence), the mount could be restored alongside the provider
  without conflict.
- Provider instance creation requires exporting the refresh token from the
  host (`gws auth export --unmasked`). When the host re-authenticates
  (`gws auth login` with new scopes), the provider instance must be
  recreated with the new refresh token.
- The audit wildcard `**.googleapis.com` in `policy.yaml` overlaps
  with the provider's enforced `oauth2.googleapis.com` endpoint. This causes
  an ambiguity validation error at sandbox creation — host matching does not
  use path specificity rules, so the overlap is rejected outright rather than
  resolved by precedence. Fixed in [ADR 3](adr0003-googleapis-subdomains-enumerated-in-audit-policy.md)
  by enumerating per-service subdomains and omitting `oauth2.googleapis.com`.

## References

- [`provider-profiles/provider-gws-oauth.yaml`](../provider-profiles/provider-gws-oauth.yaml) — provider profile
- [`run-exoshell-agent.sh`](../run-exoshell-agent.sh) — launcher script
- [`policy.yaml`](../policies/policy.yaml) — portable sandbox policy
- [SPEC.md §1](../SPEC.md) — security goals
- googleworkspace/cli#857 — env-var precedence bug
- [OpenShell policy-schema.mdx `request_body_credential_rewrite`](https://docs.openshell.nvidia.com/reference/policy-schema) — proxy body rewrite
