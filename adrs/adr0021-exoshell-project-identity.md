---
status: accepted
date: 2026-09-24
author: Tomas Mlcoch
topics:
  - identity
---

# 21. Adopt the ExOShell project identity

## Context

The project began as a personal OpenShell configuration and used personal
names for its repository identity, launcher, local configuration, sandbox
labels, and generic OCI image. Those names obscure which assets are portable
project interfaces and make the repository difficult to reference consistently.

OpenShell remains the upstream sandbox platform and CLI. Rebranding this
project must not rename OpenShell-specific commands, policy concepts, or
configuration paths owned by OpenShell itself.

## Decision

We will use ExOShell, meaning "Exoskeleton for OpenShell", as the project
identity. User-facing text will use `ExOShell`; project-controlled identifiers
will use lowercase `exoshell`.

The launcher and local configuration will be named `run-exoshell-agent.sh` and
`.exoshell.local.toml`. The portable base image will be
`exoshell-base`, the local ownership layer will be `exoshell-local`, and
launcher-created sandboxes will have `managed-by=exoshell` labels.

We will retain `openshell` in upstream CLI commands and paths controlled by
OpenShell, including `~/.config/openshell`.

## Consequences

- Existing local configuration must be renamed to `.exoshell.local.toml`.
- Existing OCI images must be rebuilt under the new tags.
- Retained sandboxes with `managed-by=my-openshell` remain discoverable only
  with their original selector.
- The rename does not change the boundary between portable and downstream
  configuration; separating those concerns is future work.

## References

- [Launcher](../run-exoshell-agent.sh)
- [Launcher implementation](../scripts/exoshell_agent.py)
- [Architecture](../ARCHITECTURE.md)
