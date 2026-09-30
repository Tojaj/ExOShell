---
status: accepted
date: 2026-09-10
author: Tomas Mlcoch
topics:
  - policy
  - providers
  - github
  - graphql
---

# 1. Declare the GitHub /graphql endpoint exactly once, in sandbox policy

## Context

OpenShell enforces REST and GraphQL L7 policies differently. REST allows are a
**union** across all matching policies: if any policy permits `POST /repos/…`,
the request goes through. GraphQL is an **intersection**: once any matching
endpoint carries `protocol: graphql`, `request_denied_for_endpoint` fires if
that endpoint does not allow the operation (`sandbox-policy.rego:355-361`), and
`deny_request` fires if any matching policy denies. The practical consequence is
that a second `/graphql` entry can only ever *narrow* the first — it cannot add
mutations that the first denies.

The `policy-overlays/` directory exists so that an AI agent's access to GitHub
writes can be granted on demand (per session) and revoked afterwards. This
requires an overlay to be able to widen the GraphQL permission, which is
impossible if the built-in `github` provider profile already declares a
query-only `/graphql` endpoint.

Three options were considered:

**Option A — add a user-policy overlay to the built-in `github` profile.**
Attach a user-policy overlay with a second `/graphql` endpoint
allowing mutations. This is what `policy-overlays/github-issues-prs.yaml`
originally attempted. It cannot work. The intersection semantics mean the
overlay's mutation endpoint is denied by the provider's query-only endpoint,
and the provider's query endpoint is denied by the overlay's mutation-only
endpoint. After the overlay was applied, `gh auth status` started reporting
"invalid token" (its query was newly denied) while `createIssue` stayed
denied. Option A fails completely.

**Option B — declare `/graphql` with read-write access in the provider
profile.** Create a custom `github-cli` profile with
`access: read-write` on the `/graphql` endpoint. This makes mutations available
from the moment the sandbox is created — there is no off state. Making it
off-by-default would require an overlay that narrows it, but the intersection
semantics invert the model: the baseline would fail open the moment the
restricting overlay was forgotten. Option B is always-on and cannot be gated.

**Option C — two provider instances.** Create `gh-personal-ro` (`--type github`,
read-only) and `gh-personal-rw` (`--type github-cli`, read-write), choosing one
at sandbox creation. This is not a mid-session toggle: switching requires
`openshell sandbox delete` + `openshell provider delete/create` + rerun of
`run-exoshell-agent.sh`. It is also a permanent policy stance, not a per-task
grant. Option C is ruled out for the same reason as B.

The solution is to keep the provider profile responsible for credentials and
REST/git rules, and to declare `/graphql` in **user policy** (in
`policy.yaml`). Then the intersection has nothing to intersect with.
The single `/graphql` entry starts at `access: read-only` (baseline = queries
only), and applying an overlay replaces it wholesale with an explicit `rules`
list that adds mutations. Reverting removes the overlay and restores the baseline
in a hot reload — no sandbox recreate needed.

This approach is viable because of two mechanisms verified in source:

- `path_selector_specificity` (`ambiguity.rs:408`) returns the count of
  non-wildcard characters in an endpoint path. `/graphql` scores 8; the
  provider profile's path-less REST endpoint scores 0. `ambiguity.rs:88-97`
  only compares `protocol`, `enforcement`, and `credential_binding.provider`
  when specificities are equal — so the user-policy `/graphql` endpoint and the
  provider's path-less REST endpoint coexist without conflict.
- `CredentialedEndpointScope` is keyed on `{host, ports}` only
  (`grpc/policy.rs:2839`). `stamp_provider_credentialed_endpoints` therefore
  stamps the user-policy `/graphql` endpoint as `provider_credentialed` (and
  hence injects `GITHUB_TOKEN`) even though `/graphql` is no longer in the
  profile — the token rewrite is governed by host:port scope, not by which
  endpoint object declared it.

There is an upstream documentation discrepancy relevant to this decision:
`OpenShell/skills/generate-sandbox-policy/SKILL.md:236-240` states that both
`*` and `**` may cross `/` boundaries and maps `/repos/{owner}/{repo}/issues`
to the glob `/repos/*/issues`. This contradicts `sandbox-policy.rego:740`
(`glob.match(pattern, ["/"], path)`) and OpenShell's own unit test
`glob_pattern_no_cross_segment`. Every REST glob in the original overlay
suffered from this one-segment-short error. The correct shape is
`/repos/*/*/issues`.

## Decision

We will declare the `/graphql` endpoint for `api.github.com` **exactly once**,
in `policy.yaml` under the `github_graphql` network policy key, with
`access: read-only` as the baseline. The `github-cli` provider profile will
carry the `api.github.com` REST endpoint (for credential binding and read-only
REST), the `github.com` git transport rules, and the credential definition —
but no `/graphql` endpoint.

Overlays in `policy-overlays/` will replace the `github_graphql` key wholesale
to widen GraphQL permissions (e.g. adding mutations for issue and PR creation),
and reverting restores the selected policy baseline via a hot reload.

`policy-overlays/apply.py` enforces the single-`/graphql` invariant at
composition time and refuses to apply if more than one endpoint with
`host: api.github.com` and `path: /graphql` is detected in the composed policy.

## Consequences

**Positive:**
- Issues and PR creation (`gh issue create`, `gh pr create`) can be granted
  on demand and revoked per session without a sandbox recreate.
- `gh auth status` (a GraphQL query) works at baseline and continues to work
  when the write overlay is active, because the overlay explicitly includes
  `allow: { operation_type: query }`.
- Credential injection (`GITHUB_TOKEN`) is unaffected.

**Negative / constraints:**
- The `/graphql` declaration now travels with the `--policy` file
  (`policy.yaml` or a local policy), not with the provider. A sandbox created from a
  different policy file without a `github_graphql` entry will have no GraphQL
  access at all — `gh auth status` fails, `gh issue list` fails.
- The `github-cli` profile is a copy of the built-in `github.yaml` minus the
  `/graphql` endpoint. If OpenShell ships an update to `providers/github.yaml`
  (new credentials, new git rules, new binaries), the local copy must be
  reviewed and updated manually. The provider profile update procedure is in
  [`providers.md`](../providers.md).
- A one-time migration is required: `openshell sandbox delete <sandbox-name>`,
  `openshell provider delete gh-personal`, and recreation with
  `--type github-cli`.
- Two invariants must be maintained by any future overlay:
  - **Single `/graphql`:** never add a second endpoint with
    `host: api.github.com` and `path: /graphql` to any overlay or to
    `policy.yaml`.
  - **Equal-specificity enforcement:** path-less endpoints (specificity 0) on
    `api.github.com:443` in user policy must use `enforcement: enforce` to match
    the provider profile's REST endpoint. `enforcement: audit` on a path-less
    endpoint is rejected by ambiguity.rs and produces an opaque server error.
  `apply.py` catches both before calling the server.

## References

- [`provider-profiles/provider-github-cli.yaml`](../provider-profiles/provider-github-cli.yaml) — the custom profile
- [`policy-overlays/github-issues-prs.yaml`](../policy-overlays/github-issues-prs.yaml) — the write overlay
- [`policy-overlays/apply.py`](../policy-overlays/apply.py) — overlay script
- OpenShell source: `crates/openshell-policy/src/ambiguity.rs:88-97`
- OpenShell source: `crates/openshell-server/src/grpc/policy.rs:2839,2970`
- OpenShell source: `crates/openshell-supervisor-network/data/sandbox-policy.rego:355-361,740`
- OpenShell source (upstream doc bug): `skills/generate-sandbox-policy/SKILL.md:236-240`
