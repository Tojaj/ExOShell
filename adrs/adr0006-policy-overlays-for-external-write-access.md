---
status: accepted
date: 2026-09-11
author: Tomas Mlcoch
topics:
  - policy
  - access-control
---

# 6. Grant external write access via policy overlays, not baseline policy

## Context

An AI agent running inside an OpenShell sandbox interacts with external services
— GitHub (issues, PRs, push), GitLab, Jira, and others. Each interaction
category can be read-only (listing issues, fetching code) or read-write
(creating issues, pushing commits, commenting on PRs). The question is when and
how write access should be granted.

Three approaches were considered:

**Option A — grant read-write access in the baseline policy.**
Define all external write permissions directly in the baseline policy so they
are available from sandbox creation. This is the simplest setup: one file, no
runtime changes. The problem is that the agent can create issues, push code, or
post comments from the moment it starts, regardless of whether the user intended
any of that for the current task. A coding assistant asked to refactor a function
could autonomously file issues, open PRs, or push branches without the user ever
requesting it. There is no off switch short of editing the policy file and
recreating the sandbox.

**Option B — use separate sandboxes for read-only and read-write.**
Create two sandbox configurations: one with read-only external access and one
with read-write. The user would choose which one to launch. This requires
`openshell sandbox delete` + recreate to switch modes — destroying the running
session, losing in-memory state, and interrupting work. It is a binary choice
made at session start with no mid-session adjustment, and no granularity (all
writes or no writes). It also doubles the number of sandbox configurations to
maintain.

**Option C — grant write access on demand via policy overlays.**
Keep the baseline policy read-only for all external
services. Define write permissions as composable overlay files in
`policy-overlays/`. The user applies overlays at runtime with `apply.py` to
grant specific write capabilities, and reverts to baseline when done. OpenShell's
`policy set` hot-reloads the policy without restarting the sandbox.

Option C is the only approach that satisfies all three requirements:

1. **Default-deny for external writes.** The agent cannot modify external state
   unless the user explicitly opts in.
2. **Granular grants.** Issue/PR authorship, git push, and future services
   (GitLab, Jira) are separate overlays that can be combined independently.
3. **Mid-session toggle.** Permissions can be granted and revoked during a
   running session without destroying the sandbox.

The overlay model follows the principle of least privilege: the agent starts with
the minimum access needed for read-only work, and write access is elevated only
when the user decides it is needed, for exactly the scope they choose.

### Current overlays

| Overlay | What it grants | What it does NOT grant |
|---------|---------------|-----------------------|
| `github-issues-prs.yaml` | Issue and PR create/comment/edit/close via GraphQL mutations and REST | `mergePullRequest`, `git push`, any DELETE, destructive mutations |
| `github-push.yaml` | `POST /**/git-receive-pack` on `github.com` (HTTPS push) | Any API calls (those come from the provider and `github-issues-prs.yaml`) |
| `github-graphql-audit.yaml` | Debugging: switches `/graphql` to audit mode | Not for production use |

### Planned overlays

GitLab issue/MR authorship, Jira issue creation and commenting, and other
external services will follow the same pattern: read-only baseline, write
overlay, `apply.py` composition.

### Defence in depth

Policy overlays are one layer. Even when an overlay grants an OpenShell-level
permission, the underlying token may not have the required scope. For example,
`github-push.yaml` allows `git-receive-pack` through the proxy, but a
fine-grained token with only Contents: Read still causes GitHub to reject
the push. Token scope is a second gate that must also be configured.

## Decision

We will keep the baseline sandbox policy read-only for
all external services. Write access to external services will be granted
exclusively through composable policy overlays applied at runtime via
`policy-overlays/apply.py`.

Each external service or write category will have its own overlay file. Overlays
are designed to be combined (`apply.py --sandbox NAME github-issues-prs.yaml
github-push.yaml`) and reverted (`apply.py --sandbox NAME --revert`) without
sandbox recreation. The baseline is the implicit revert target: `apply.py
--sandbox NAME --revert` restores the policy selected in
`.exoshell.local.toml` (or `policy.yaml` when none is configured), including its
`network_policies` verbatim.

New external write capabilities (GitLab, Jira, etc.) will follow this pattern:
read-only in the baseline, write overlay in `policy-overlays/`, documented in
`policy-overlays/README.md`.

## Consequences

**Positive:**

- The agent cannot create, modify, or delete external resources (issues, PRs,
  branches, comments) unless the user explicitly applies the corresponding
  overlay. This prevents unintended side effects from autonomous agent behaviour.
- Write access is granular: issue authorship, git push, and future services are
  independent grants. The user can allow PR creation without allowing push, or
  vice versa.
- Permissions can be granted and revoked mid-session. A typical workflow is:
  apply the overlay, perform the write operation, revert. The sandbox stays
  running throughout.
- Adding a new external service follows a repeatable pattern: add audit endpoints
  to the baseline for read access, create a write overlay, update `apply.py`
  invariant checks if needed.
- Defence in depth: even with an overlay active, the underlying token scope is a
  second gate. A misconfigured overlay cannot exceed what the token allows.

**Negative / constraints:**

- The user must remember to apply overlays before write operations. An agent
  asked to "create an issue" will fail if the overlay is not active. This is the
  intended behaviour — the failure is the prompt to consciously grant access —
  but it adds a manual step.
- Each new external service requires authoring an overlay file, testing it
  against the live sandbox, and documenting it. The `apply.py` invariant checks
  and the overlay README reduce the risk of misconfiguration but do not
  eliminate authoring effort.
- `apply.py` must be kept in sync with OpenShell's policy validation rules
  (ambiguity checks, `access`/`rules` mutual exclusion, GraphQL intersection
  semantics). Changes to OpenShell's policy engine may require updates to the
  pre-flight checks.
- The overlay model currently covers only `network_policies`. Filesystem and
  process policy sections are always taken from the live sandbox state and cannot
  be overridden by overlays (this is enforced by `apply.py`).

## References

- [`policy.yaml`](../policies/policy.yaml) — portable baseline policy (read-only for external services)
- [`policy-overlays/README.md`](../policy-overlays/README.md) — overlay documentation and invariants
- [`policy-overlays/apply.py`](../policy-overlays/apply.py) — overlay composition and application script
- [`policy-overlays/github-issues-prs.yaml`](../policy-overlays/github-issues-prs.yaml) — GitHub issue/PR write overlay
- [`policy-overlays/github-push.yaml`](../policy-overlays/github-push.yaml) — GitHub push overlay
- [ADR 1](adr0001-graphql-endpoint-declared-once-in-user-policy.md) — single `/graphql` endpoint invariant (prerequisite for overlay-based GraphQL toggling)
