---
status: accepted
date: 2026-09-14
author: Tomas Mlcoch
topics:
  - providers
  - credentials
  - codex
---

# 8. Custom Codex provider profile with `allow_uninspected_credentials` on conversation endpoints

## Context

The built-in `codex` provider profile marks `api.openai.com` as a credentialed
REST endpoint (`protocol: rest`, `access: read-write`, `enforcement: enforce`)
and leaves both `request_body_credential_rewrite` and
`allow_uninspected_credentials` at their default of `false`.

With those defaults, the sandbox proxy streams every POST body and fail-closes
on the first byte matching OpenShell's placeholder syntax
(`openshell:resolve:env:…`). The check is purely syntactic — it does not
consider which provider owns the placeholder or whether the placeholder is
resolvable at the destination.

When Codex shares a sandbox with a second provider (e.g. `github` for `gh` /
`git`), routine commands echo credential placeholders:

```
$ gh auth status
Token: openshell:resolve:env:<opaque-id>_GITHUB_*****
```

Codex includes tool output in the next model request. The GitHub placeholder
enters the `/v1/responses` JSON body and the proxy denies it:

```
[sandbox] NET:TRAFFIC [HIGH] DENIED api.openai.com:443
          [reason:POST request body credential traffic denied for api.openai.com:443]
```

Because the placeholder stays in conversation history, every subsequent request
in the session is denied. The same failure occurs with the built-in
`claude-code` and `copilot` profiles.

Built-in profiles are immutable — the gateway rejects updates with *"managed by
source 'builtin' and cannot be updated"* — so the flag cannot be changed
without a custom profile.

`allow_uninspected_credentials: true` on the conversation hosts was the
approach chosen. `request_body_credential_rewrite: true` was noted as a
superficially related flag but was not evaluated as a real option: if the proxy
successfully resolved a foreign placeholder in the request body it would
substitute the real credential — sending the actual GitHub token to OpenAI —
which is a data-exfiltration risk worse than the original problem. The flag is
the right tool when you want body-level secret injection for the *same*
provider; it is the wrong tool here.

## Decision

We will use a custom profile (`provider-profiles/provider-codex-cli.yaml`) with
`allow_uninspected_credentials: true` on the three conversation hosts
(`api.openai.com`, `chatgpt.com`, `ab.chatgpt.com`). The flag is deliberately
omitted on `auth.openai.com` so that OAuth token-refresh bodies remain
inspected.

The result: foreign placeholders are forwarded to OpenAI as opaque strings.
The real credential is never sent anywhere — it was never substituted — and
header rewrite for `OPENAI_API_KEY` is unaffected.

## Consequences

**Positive:**
- Multi-provider sessions (codex + github) work without session-breaking denials.
- No real credentials leak to the wrong endpoint: the opaque placeholder is
  what OpenAI receives, not the resolved secret.
- Header rewrite for `OPENAI_API_KEY` is unchanged.

**Negative / constraints:**
- The custom profile must be re-synced if upstream changes the built-in codex
  profile (endpoints, binaries, credentials). This is a known cost of the
  built-in immutability constraint.
- `allow_uninspected_credentials` is coarser than a binding-aware fix: it
  disables body scanning for all placeholders on those hosts, not only foreign
  ones. The upstream bug (NVIDIA/OpenShell#3237) tracks a proper binding-aware
  check that would make this workaround unnecessary.

## References

- [`provider-profiles/provider-codex-cli.yaml`](../provider-profiles/provider-codex-cli.yaml) — custom profile
- [NVIDIA/OpenShell#3237](https://github.com/NVIDIA/OpenShell/issues/3237) — upstream bug: body scan denies foreign-provider placeholders
