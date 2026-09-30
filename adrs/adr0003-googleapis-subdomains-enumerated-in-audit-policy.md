---
status: accepted
date: 2026-09-11
author: Tomas Mlcoch
topics:
  - policy
  - gws
---

# 3. Enumerate googleapis.com subdomains in audit policy

## Context

After deploying the `gws-oauth` provider ([ADR 2](adr0002-gws-credentials-via-provider-body-rewrite.md)),
sandbox creation failed with:

```
network endpoint ambiguity validation failed:
network policies '_provider_gws_oauth' endpoint[0] (oauth2.googleapis.com:443)
and 'agent-general-audit' endpoint[24] (**.googleapis.com:443) overlap on
port(s) 443 with conflicting metadata:
  enforcement="enforce" vs "audit";
  request_body_credential_rewrite=true vs false
```

The `gws-oauth` provider enforces `oauth2.googleapis.com:443` with
`request_body_credential_rewrite: true`. The `agent-general-audit` section in
`policy.yaml` had `**.googleapis.com:443` in audit mode. The wildcard
matches `oauth2.googleapis.com`, and OpenShell's ambiguity validator rejects
overlapping endpoints when `enforcement` or `request_body_credential_rewrite`
differ — regardless of whether one selector is more specific than the other.

ADR 2 (Consequences, bullet 5) assumed that host specificity would resolve
this overlap the way path specificity resolves the `/graphql` coexistence in
[ADR 1](adr0001-graphql-endpoint-declared-once-in-user-policy.md). That
assumption was wrong: `path_selector_specificity` (`ambiguity.rs:408`) applies
to the path component only. Host matching is a glob comparison
(`ambiguity.rs:88-97`), and `**.googleapis.com` vs `oauth2.googleapis.com`
overlap at equal precedence — triggering the ambiguity error.

Three options were considered:

**Option A — enumerate subdomains.** Replace `**.googleapis.com` with the
explicit list of googleapis.com subdomains that gws CLI actually uses, omitting
`oauth2.googleapis.com` (owned by the provider). The gws CLI source
(`crates/`) references ~28 subdomains. A `**.rep.googleapis.com` wildcard
covers the multi-level Model Armor regional endpoints
(`modelarmor.{region}.rep.googleapis.com`), which do not conflict with the
provider. Correct and explicit, but requires a policy update when gws adds a
new Google API.

**Option B — change audit to enforce on the wildcard.** Matching the
provider's `enforcement: enforce` would resolve the enforcement conflict but
not the `request_body_credential_rewrite` conflict. The ambiguity validator
checks both. Option B fails.

**Option C — remove all googleapis.com audit entries.** The provider covers
`oauth2.googleapis.com` in enforce mode, and `**.google.com` in audit covers
other Google hosts. The `gws-oauth` provider handles the exact
`accounts.google.com/o/oauth2/token` path at a higher path specificity.
However, all per-service API traffic (`sheets.googleapis.com`,
`drive.googleapis.com`, etc.) would become invisible to audit. Option C is too
broad a loss.

## Decision

We will use Option A: enumerate the googleapis.com subdomains explicitly in
`policy.yaml`, omitting `oauth2.googleapis.com`. The list is derived
from the gws CLI source (`crates/`) at version 0.22.5. A comment in the
policy file explains why the wildcard cannot be used.

The `**.rep.googleapis.com` wildcard is safe because it does not overlap with
any provider endpoint — `oauth2.googleapis.com` is not under `.rep.`.

ADR 2 is updated to correct the specificity assumption and cross-reference
this ADR.

## Consequences

**Positive:**
- Sandbox creation succeeds with `--provider gws-oauth` and the
  `agent-general-audit` policy active simultaneously.
- All per-service Google API traffic remains visible in audit logs.
- The `gws-oauth` provider's `request_body_credential_rewrite` continues to
  function without interference.

**Negative / constraints:**
- When gws CLI adds support for a new Google API (new `*.googleapis.com`
  subdomain), the subdomain must be added to `policy.yaml` manually.
  Until then, requests to the new API subdomain will be blocked (not
  audited). Check for new subdomains when bumping `GWS_VERSION` in the
  Dockerfile:
  ```
  grep -rh 'googleapis\.com' crates/ --include="*.rs" \
    | grep -oP '[a-z0-9_.-]+\.googleapis\.com' | sort -u
  ```
- The policy file grows by ~25 lines compared to the single-wildcard form.
  This is a readability trade-off for correctness.

## References

- [`policy.yaml`](../policies/policy.yaml) — portable sandbox policy (the fix)
- [`provider-profiles/provider-gws-oauth.yaml`](../provider-profiles/provider-gws-oauth.yaml) — the provider that owns `oauth2.googleapis.com`
- [ADR 1](adr0001-graphql-endpoint-declared-once-in-user-policy.md) — path specificity (works for `/graphql`; does not apply to host matching)
- [ADR 2](adr0002-gws-credentials-via-provider-body-rewrite.md) — gws-oauth provider (corrected re: host specificity)
- OpenShell source: `crates/openshell-policy/src/ambiguity.rs:88-97` — host overlap detection
- OpenShell source: `crates/openshell-policy/src/ambiguity.rs:408` — `path_selector_specificity` (path only, not host)
