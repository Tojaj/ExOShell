---
status: accepted
date: 2026-10-08
topics:
  - launcher
  - filesystem
  - skills
---

# 38. Import user skills through disposable snapshots

## Context

Users maintain skills in home directories, other collections, and symlinked
checkouts. Mounting those sources directly does not make external symlink
targets available and couples sandbox edits to host skills. The base image
already contains shared skills that imports must preserve.

OpenShell 0.1.2 preserves uploaded symlinks and rejects creation-time uploads
with a trailing main command. Adopting native uploads would require changing
the launcher's canonical agent process and cleanup flow. The existing Podman
driver configuration supports read-only mounts, and the startup helper can
copy a prepared snapshot before agent initialization.

## Decision

We will accept an opt-in common `skills` list containing individual skill
directories or collections of immediate child skills, with repeatable
`--skill` overrides and a `--no-skills` opt-out.

We will materialize complete skills in a private temporary host snapshot,
dereferencing symlinks while preserving directory aliases and executable
permissions. Invalid sources, special files, cycles, and duplicate names will
fail before provisioning. We will mount only the snapshot read-only at
`/tmp/exoshell-skills` and copy it into `/sandbox/.agents/skills` at startup.
We will check every destination first and reject collisions with image skills.

We will retain the existing OpenShell agent launch and cleanup flow. Explicit
skill imports will also apply with `--no-share`; that option will suppress
project and kubeconfig mounts while permitting the skill snapshot mount.
Host staging will be removed when the launcher returns. Retained sandboxes
will keep their imported container copies.

We will replace Claude's per-skill links with one directory symlink to the
shared skills directory. We will grant the real directory explicit filesystem
policy access and require an image capability marker for configured imports.

## Consequences

- Host source changes after snapshotting do not propagate into the sandbox.
- Sandbox edits do not update original host skill directories.
- Whole collections that overlap image skills require selecting individual
  non-conflicting skills instead.
- Base and derived images must be rebuilt; custom policies must allow the
  snapshot to be read and the destination to be read and written.
- The snapshot uses the existing local Podman gateway filesystem arrangement.
- Native upload can be reconsidered when OpenShell supports uploads before
  canonical command startup.

## References

- [Launcher](../scripts/exoshell_agent.py)
- [Startup helper](../sandboxes/exoshell-base/exoshell-agent)
- [ADR-0037](adr0037-optional-host-sharing.md)
- [OpenShell 0.1.2 upload restriction](https://github.com/NVIDIA/OpenShell/blob/v0.1.2/crates/openshell-cli/src/run.rs)
- [OpenShell 0.1.2 upload and lifecycle documentation](https://github.com/NVIDIA/OpenShell/blob/v0.1.2/docs/how-it-works/sandboxes/overview.mdx)
- [Claude Code personal skills](https://code.claude.com/docs/en/skills#choose-where-skills-load)
