---
status: accepted
date: 2026-10-07
topics:
  - launcher
  - filesystem
  - lifecycle
---

# 37. Allow disposable workspaces without host sharing

## Context

The launcher always binds a host directory to `/workspace`. Some sessions need
to clone a repository, experiment inside the sandbox, and discard the resulting
files without exposing a host project. Configured kubeconfig mounts can also
expose host files in these sessions. The image already provides a writable
`/workspace`, and the launcher already deletes sandboxes on normal exit.

A temporary host directory would still expose host storage and require separate
cleanup. Container-local storage supports this workflow through the existing
image and OpenShell lifecycle. Project-local Git identity cannot be required
when no host project is selected.

## Decision

We will add the CLI-only `--no-share` option and start the agent in the image's
writable `/workspace` without launcher-supplied host bind mounts. The option
will suppress configured host shares and kubeconfigs before checking their
existence. Explicit `--host-share`, `--kubeconfig`, or positional host projects
will be rejected to avoid silently ignoring conflicting user instructions.

We will preserve configuration discovery, providers, policy selection, forge
settings, and the `/tmp/gws` tmpfs. OpenShell will continue managing its own
internal mounts and storage; this option controls ExOShell's host shares.

We will read only global host Git identity in this mode and inject it when both
name and email are available. Missing or partial identity will permit startup
without identity overrides; other Git configuration read failures will remain
errors. Users can configure identity inside the sandbox when needed.

We will label these sessions `project=ephemeral` and retain default deletion
with `--no-keep`. Explicit `--keep` will retain the sandbox and workspace until
later cleanup. Existing shared-project launches will retain their behavior.

## Consequences

- Cloned repositories and work can remain entirely inside the disposable sandbox.
- Configured kubeconfig access is unavailable in this mode.
- Users must push or export work before deletion if they want to preserve it.
- Optional Git identity lets users inspect repositories without host Git setup.
- No image rebuild is required for the standard image; derived images must
  supply a writable `/workspace`.
- [ADR-0038](adr0038-user-skill-snapshots.md) later permits explicitly configured
  skill snapshot mounts in this mode; project and kubeconfig mounts remain suppressed.
- Tests must cover mount suppression, conflicting arguments, optional identity,
  and the existing lifecycle for all supported agents.

## References

- [Launcher](../scripts/exoshell_agent.py)
- [Base image](../sandboxes/exoshell-base/Dockerfile)
- [ADR-0016](adr0016-multi-agent-launcher-and-ephemeral-state.md)
- [ADR-0019](adr0019-sandbox-lifecycle-for-agent-state.md)
- [ADR-0025](adr0025-podman-bind-mount-admission.md)
- [OpenShell Podman driver](https://github.com/NVIDIA/OpenShell/blob/main/crates/openshell-driver-podman/README.md)
- [OpenShell Podman driver source](https://github.com/NVIDIA/OpenShell/tree/main/crates/openshell-driver-podman/src)
