---
status: accepted
date: 2026-09-11
author: Tomas Mlcoch
topics:
  - launcher
  - identity
  - git
---

# 4. Pass Git identity via environment variables, not a provider

## Context

The sandbox launcher (`run-exoshell-agent.sh`) injects the Git committer /
author identity into the sandbox so that commits created by the agent carry
the correct `user.name` and `user.email`. The script reads these values
dynamically from the project's effective Git configuration:

```bash
git -C "$PROJECT" config --get user.name
git -C "$PROJECT" config --get user.email
```

Git's normal precedence applies: repository-local configuration wins, then
global. The values are passed as `--env` flags on `openshell sandbox create`
(nine env vars: `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`,
`GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`, `GIT_CONFIG_COUNT`,
`GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`, `GIT_CONFIG_KEY_1`,
`GIT_CONFIG_VALUE_1`).

Two approaches were considered:

**Option A — `--env` flags in the launch script (status quo).** The script
resolves the identity at launch time from the project's Git config and
passes it as ordinary environment variables. The identity is determined per
invocation and can differ between projects.

**Option B — dedicated provider profile.** Create a provider profile
(`git-identity`, `category: other`) with credentials for the name and
email, similar to the `gws-oauth` provider. The sandbox would receive
`--provider git-identity` instead of the `--env` block.

Key differences between the two:

| Concern                       | Option A (`--env`)            | Option B (provider)            |
|-------------------------------|-------------------------------|--------------------------------|
| Per-project identity          | Automatic — reads `git -C`    | Fixed at `provider create`     |
| Setup ceremony                | None — script is self-contained | One-time `provider create`; must recreate when identity changes |
| Secret hiding                 | N/A — name and email are not secrets | Provider machinery adds no value for non-secret data |
| Launch script complexity      | Nine `--env` flags            | One `--provider` flag          |

## Decision

We will keep Option A: Git identity is passed as `--env` flags, resolved
dynamically from the project's Git configuration at launch time.

The primary reason is that a provider's credentials are fixed at
`openshell provider create` time. The current script honors per-project
Git identity automatically — a repository with a project-local `user.name`
/ `user.email` gets that identity without any extra configuration. A
provider would either lock in a single identity or require recreating the
provider instance each time the project changes, adding friction with no
compensating benefit.

A secondary reason is semantic fit: provider profiles are designed for
credentials that the proxy can hide from the sandbox. Git name and email
are not secrets — routing them through the credential machinery adds
conceptual overhead without a security payoff.

## Consequences

**Positive:**
- Per-project Git identity continues to work transparently.
- No provider setup step or maintenance when the identity changes.
- The launch script remains self-contained — no external state to keep in
  sync.

**Negative / constraints:**
- The launch script carries nine `--env` flags for Git identity, which is
  verbose. This is acceptable because the flags are straightforward and
  well-commented.
- If OpenShell later supports dynamic credential resolution at launch time
  (e.g., a provider that runs a shell command to obtain values), this
  decision could be revisited.

## References

- [`run-exoshell-agent.sh`](../run-exoshell-agent.sh) — launcher script
