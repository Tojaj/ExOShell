---
status: accepted
date: 2026-09-17
author: Tomas Mlcoch
topics:
  - providers
  - gitlab
---

# 10. Set allow_encoded_slash on GitLab provider endpoints

## Context

GitLab's REST API uses URL-encoded slashes (`%2F`) in project-scoped paths, for
example `/api/v4/projects/namespace%2Frepo/snippets/123`. The sandbox L7 engine
rejects such requests by default with:

> `HTTP request-target rejected: request-target contains an encoded '/' (%2F)
> which is not allowed on this endpoint`

Without `allow_encoded_slash: true`, any project-scoped API path fails, while
global (non-project-scoped) paths like `/api/v4/snippets/123` succeed. The fix
is to set the flag on the endpoint; there is no workaround at the `glab`/`curl`
call site because the encoding is required by the GitLab API spec.

## Decision

We will add `allow_encoded_slash: true` to the `gitlab.com:443` endpoint in
`provider-gitlab-cli.yaml` (and in any per-instance profile, e.g.
`provider-gitlab-example-cli.yaml`).

## Consequences

**Positive:**

- Project-scoped API paths work as expected (`glab api`, `curl`, coding agents).
- No change to the permission model: the existing `GET **` / `POST
  /**/git-upload-pack` rules still govern which paths are reachable.

**Negative / constraints:**

- The flag must be remembered when authoring any future per-host GitLab profile.

## References

- [`provider-profiles/provider-gitlab-cli.yaml`](../provider-profiles/provider-gitlab-cli.yaml)
- [ADR 9](adr0009-gitlab-provider-graphql-in-user-policy.md) — GitLab provider design
