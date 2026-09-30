---
status: accepted
date: 2026-09-24
author: Tomas Mlcoch
topics:
  - launcher
  - github
  - gitlab
---

# 20. Select supported Git forge hosts in the launcher

## Context

Provider profiles bind credentials and endpoint rules to a specific host, while
the GitHub and GitLab CLIs need a selected default host for API and Git
operations. GitLab host selection was already performed by the launcher, but
GitHub host selection and its Git credential helper had to be baked into a
host-specific sandbox image. That made equivalent custom-provider setups use
different configuration layers.

The two forges do not have identical client behavior. GitLab also requires a
token-free `glab` host record in the image, while GitHub's `gh` can select a
host with `GH_HOST` and supply Git credentials through `gh auth git-credential`.
Future forge CLIs may differ further in their host bootstrap, credential, API,
and Git transport requirements.

## Decision

We will keep explicit launcher settings for each supported forge host. The
launcher will configure GitHub with `GH_HOST`, its environment-backed Git
credential helper, and an SSH-to-HTTPS remote rewrite. It will retain the
existing GitLab host selection, credential helper, and rewrite behavior.

Provider profiles and sandbox policies will remain host-specific. Selecting a
forge host will not create a provider, inject a credential, or grant network
access. We will not introduce a generic forge-host setting or registry until a
third supported forge demonstrates a shared, stable configuration contract.

## Consequences

- Users can select a GitHub Enterprise Server host without a host-specific
  image solely for `GH_HOST` and Git credential configuration.
- Images remain responsible for non-secret CLI bootstrap that the launcher
  cannot provide, including GitLab's token-free host registration and custom
  trust roots.
- Each source-control host still requires a dedicated provider profile and
  GraphQL policy entry because OpenShell credential binding and enforcement are
  host-specific.
- Additional forges will add explicit settings first; a generic abstraction
  requires evidence that their runtime requirements are compatible.

## References

- [Launcher implementation](../scripts/exoshell_agent.py)
- [Customization guide](../CUSTOMIZATION.md)
- [ADR-0012](adr0012-bake-token-free-glab-host-config.md)
