---
status: accepted
date: 2026-09-16
author: Tomas Mlcoch
topics:
  - policy
  - providers
  - gitlab
  - graphql
---

# 9. Declare GitLab /api/graphql in user policy, same pattern as GitHub

## Context

We are adding GitLab provider support to the sandbox, following the overlay
model established in ADR 1 and ADR 6. The question is whether the same GraphQL
intersection problem from ADR 1 applies to GitLab, and how to handle multiple
GitLab instances.

### Does the intersection problem apply?

Yes. The mechanism is identical: OpenShell's Rego enforces GraphQL allows as an
intersection across all matching endpoints (`sandbox-policy.rego:327-331`).
If a provider profile declares an endpoint with `path: /api/graphql` and
`protocol: graphql`, any user-policy `/api/graphql` endpoint on the same host
enters intersection semantics. A second `/api/graphql` entry can only ever
narrow the first — it cannot add mutations the first denies. This is the same
constraint that forced the custom `github-cli` profile in ADR 1.

### Key differences from GitHub

1. **No built-in profile.** OpenShell has no `gitlab.yaml` in its `providers/`
   directory. The Rust code (`gitlab.rs`) only defines credential discovery
   (`GITLAB_TOKEN`, `GLAB_TOKEN`, `CI_JOB_TOKEN`). A custom profile must be
   authored from scratch — there is no built-in to strip down.

2. **Different GraphQL path.** GitLab's GraphQL endpoint is `/api/graphql`
   (path specificity 12), not `/graphql` (specificity 8). Both have
   specificity > 0, so neither conflicts with path-less (specificity 0) REST
   endpoints in `ambiguity.rs`.

3. **Single host.** GitHub separates `api.github.com` (REST/GraphQL) from
   `github.com` (git transport). GitLab serves REST API (`/api/v4/`), GraphQL
   (`/api/graphql`), and git transport all on `gitlab.com:443`. The provider
   profile uses a single endpoint with explicit `rules` (not `access`) to
   combine read-only REST with `git-upload-pack`.

4. **REST-first CLI.** `glab issue create`, `glab mr create`, and all
   comment/edit commands use REST (`go-gitlab` client), not GraphQL mutations.
   `glab auth status` calls `/api/v4/user` (REST). GraphQL is used only by
   `glab api graphql` and `glab workitems list`. This means the baseline works
   for most operations even without any GraphQL endpoint — a simpler situation
   than GitHub where `gh auth status` requires GraphQL.

5. **Multiple instances.** Users may work with `gitlab.com` and one or more
   self-hosted instances simultaneously. Each instance has its own host, token,
   and GraphQL endpoint, requiring a per-instance provider and per-instance
   policy entries.

### Multi-instance design

Each GitLab instance requires three things:

1. **A provider instance** using the same `gitlab-cli` profile type, with its
   own name and credential. The profile is host-agnostic: the host field in
   the endpoint declaration is set once in the profile and cannot be
   parameterised at provider-create time. This means a separate profile YAML
   is needed per unique host (e.g. `provider-gitlab-cli.yaml` for
   `gitlab.com`, `provider-gitlab-internal-cli.yaml` for a self-hosted
   instance). The profile ID must also differ (`gitlab-cli` vs
   `gitlab-internal-cli`).

2. **A `/api/graphql` entry** in the selected sandbox policy under a unique
   `network_policies` key. The key name encodes the instance
   (`gitlab_com_graphql`, `gitlab_internal_graphql`). Each key is independently
   replaceable by overlays.

3. **Instance-specific overlays** in `policy-overlays/`. An overlay targeting
   `gitlab_com_graphql` does not affect `gitlab_internal_graphql`, so write
   access can be granted per-instance.

The `apply.py` invariant check enforces at most one endpoint per host with
`protocol: graphql` and the same path, catching accidental duplicates across
overlays.

## Decision

We will follow the same pattern as ADR 1: declare the GitLab `/api/graphql`
endpoint **exactly once per host**, in the selected sandbox policy under a named
network policy key (e.g. `gitlab_com_graphql`), with `access: read-only` as
the baseline.

The `gitlab-cli` provider profile will carry only the REST + git transport
endpoint for credential binding — no `/api/graphql` endpoint. For each
additional GitLab instance, a separate profile YAML and provider instance will
be created with the instance's host.

Overlays in `policy-overlays/` will replace the per-instance GraphQL key
wholesale to widen permissions (e.g. adding mutations for work item creation),
and reverting restores the baseline via hot reload.

`apply.py` will enforce the single-GraphQL-per-host invariant at composition
time: at most one endpoint with `protocol: graphql` and the same
`(host, path)` tuple may exist in the composed policy.

When the `gitlab.com` audit entries in `agent_general` are replaced by the
enforcing provider, they must be removed from that policy to avoid
the audit/enforce overlap that `ambiguity.rs` rejects.

## Consequences

**Positive:**

- The same overlay model works for GitLab as for GitHub: read-only baseline,
  write overlay, hot-reload toggle, no sandbox recreate.
- Each GitLab instance is independently controllable — write access to
  `gitlab.com` can be granted without affecting an internal instance.
- `glab auth status` and all issue/MR commands work at baseline (REST only).
  The GraphQL endpoint is needed only for work items and explicit
  `glab api graphql` calls.
- Credential injection (`GITLAB_TOKEN`) is unaffected — `CredentialedEndpointScope`
  is keyed on `{host, ports}`, so the token reaches `/api/graphql` even though
  that path is not in the provider profile.
- `apply.py` catches duplicate GraphQL endpoints per host before calling the
  server, preventing the intersection bug.

**Negative / constraints:**

- Each GitLab instance requires its own profile YAML (host is baked into the
  profile, not parameterisable at provider-create time). Adding a new instance
  means creating a new profile file, importing it, and adding policy entries.
- The audit entries for `gitlab.com` and `**.gitlab.com` in `agent_general`
  must be removed once the provider is attached. Forgetting this causes an
  opaque `ambiguity.rs` rejection.
- `glab` discovers its host from `~/.config/glab-cli/config.yml` and
  `GITLAB_HOST`. Inside the sandbox, the `glab` config must point to the
  correct host for the active provider. If multiple providers are attached,
  `glab` can only default to one — the user must pass `--hostname` or set
  `GITLAB_HOST` to reach the other.
- The profile currently lists only `gitlab.com`. A self-hosted instance at a
  different host requires a separate profile file — the same `gitlab-cli`
  profile ID cannot be reused for two hosts.

## References

- [`provider-profiles/provider-gitlab-cli.yaml`](../provider-profiles/provider-gitlab-cli.yaml) — the custom profile (gitlab.com)
- [`providers.md`](../providers.md) — provider setup and multi-instance guide
- [`policy.yaml`](../policies/policy.yaml) — portable baseline policy with `gitlab_com_graphql` entry
- [`policy-overlays/apply.py`](../policy-overlays/apply.py) — overlay script with per-host GraphQL invariant
- [ADR 1](adr0001-graphql-endpoint-declared-once-in-user-policy.md) — the GitHub GraphQL-in-user-policy decision this extends
- [ADR 6](adr0006-policy-overlays-for-external-write-access.md) — the overlay model for external write access
- `glab` source: `internal/glinstance/host.go:109-121` — GraphQL endpoint is `/api/graphql/`
- `glab` source: `internal/commands/auth/status/status.go:142-143` — auth status uses REST (`Users.CurrentUser`)
- `glab` source: `internal/commands/issue/create/issue_create.go:30-31` — issue create uses REST
- OpenShell source: `crates/openshell-providers/src/providers/gitlab.rs` — discovery spec only, no profile
- OpenShell source: `providers/` — no `gitlab.yaml` exists
