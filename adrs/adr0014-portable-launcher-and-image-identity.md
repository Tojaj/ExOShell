---
status: accepted
date: 2026-09-18
author: Tomas Mlcoch
topics:
  - launcher
  - sandbox-image
  - identity
---

# 14. Use stable container paths with local launcher configuration and identity

## Context

The original launcher and image encoded one host account's username, workspace
location, UID/GID, provider set, and optional integrations. That made the setup
convenient on one machine but unsafe to publish and difficult to reuse.

OpenShell's OCI workspace remains `/sandbox` and cannot be replaced by a bind
mount in the current driver. Rootless Podman also needs the container process's
numeric identity to match the owner of a writable host share. Those constraints
separate portable container paths from machine-specific source paths and IDs.

Machine defaults could remain in shell code, be loaded by sourcing a shell
fragment, or use a data-only configuration file. Shell code is not portable,
and sourcing configuration executes it. TOML is data-only and Python 3.11 can
parse it without another dependency.

## Decision

We will use `/workspace` as the mounted host-share target and reuse the
community image identity: user `sandbox`, home `/sandbox`, Codex state at
`/sandbox/.codex`. `/sandbox` remains the OCI workdir and home; the launcher
will translate the canonical project path relative to the canonical share and
explicitly change into the resulting `/workspace` path.

We will keep machine defaults in an ignored `.exoshell.local.toml`, with a
committed generic example and command-line overrides. Optional files and
integrations will not be enabled by public defaults.

We will keep the community `sandbox` account in generic image layers, then use
a thin local image layer to change that account to the host UID/GID. Shared
image sources will contain neither a host username nor personal numeric IDs.
OpenShell policy identity remains `sandbox`, the only named value the schema
accepts besides a numeric UID/GID.

## Consequences

- Shared launcher, image, policy, and documentation paths are host-independent.
- Projects may be selected anywhere below a configurable host share, but host
  absolute paths embedded in project content do not carry into the sandbox.
- Local configuration adds schema validation and a Python 3.11 prerequisite.
- Each machine must build the small UID/GID layer before using writable bind
  mounts with a local image.
- Optional integration configuration remains explicit and testable.
- A future extension/profile contract can compose richer site-specific
  behavior without changing this portable core.

## References

- [Launcher](../run-exoshell-agent.sh)
- [Generic image](../sandboxes/exoshell-base/)
- [Local identity layer](../sandboxes/local-user/)
- [ADR-0015](adr0015-host-uid-remap-not-keep-id.md) — why `keep-id` does not replace that layer
