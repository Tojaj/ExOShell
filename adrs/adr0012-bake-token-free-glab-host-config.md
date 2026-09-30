---
status: accepted
date: 2026-09-18
author: Tomas Mlcoch
topics:
  - sandbox-image
  - gitlab
---

# 12. Bake token-free glab host configuration into sandbox images

## Context

The `glab` CLI needs a local host entry before `glab auth status` will use
the provider-supplied `GITLAB_TOKEN` environment placeholder. Providers v2
bind and substitute credentials on authorized outbound requests, but do not
manage sandbox-local CLI configuration.

The host configuration can be included in the image, written by a launcher at
sandbox start, or obtained through `glab auth login`. Mounting the host
configuration would also provide the entry, but can expose a locally stored
personal token.

## Decision

We will bake small, token-free `config.yml` templates into the sandbox images.
`exoshell-base` will register the public GitLab host; any custom-image variant
can replace that file with one registering other gitlab hosts. The files will
be owned by the sandbox user with mode `0600` at `/etc/glab-cli/config.yml`.
This is required by `glab`, which performs the same permission check even for
a token-free configuration. The enclosing directory remains root-owned, so
the user cannot atomically replace the image-provided template.

`exoshell-base` will set `GLAB_CONFIG_DIR=/etc/glab-cli` explicitly and disable
`glab` update checks with `GLAB_CHECK_UPDATE=false`. Launchers will select the
desired host with `GITLAB_HOST`; the provider remains the sole source of the
credential.

## Consequences

- Sandboxes do not need a networked login or mutable bootstrap step before
  using `glab`.
- The checked-in configuration is easily reviewed to confirm it contains host
  metadata only, not a credential.
- Image rebuilds are required after changing host metadata.
- `glab auth status --all` may probe a registered host without an attached
  provider. Normal commands and plain `glab auth status` follow `GITLAB_HOST`.

## References

- [`sandboxes/exoshell-base/Dockerfile`](../sandboxes/exoshell-base/Dockerfile)
- [`sandboxes/exoshell-base/glab-config.yml`](../sandboxes/exoshell-base/glab-config.yml)
- [ADR 0005](adr0005-custom-sandbox-image.md) — custom sandbox image
