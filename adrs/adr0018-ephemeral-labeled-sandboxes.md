---
status: accepted
date: 2026-09-23
author: Tomas Mlcoch
topics:
  - launcher
  - sandbox-lifecycle
---

# 18. Use gateway-generated names and ephemeral labeled sandboxes

## Context

The launcher currently assigns a fixed sandbox name from configuration or the
selected agent. OpenShell retains sandboxes by default, so later launches using
the same name fail. Fixed names also prevent multiple agents from running
concurrently.

Deriving unique names in the launcher would require normalization, allocation,
and race handling while remaining within OpenShell's 19-character sandbox-name
limit. Local locking would not coordinate clients using the same gateway from
different machines.

OpenShell can generate sandbox names, delete foreground sandboxes after their
main process exits, and attach labels that support selector-based listing.

## Decision

We will omit `--name` and allow the OpenShell gateway to generate each sandbox
name.

Every launcher-created sandbox will receive these labels:

- `managed-by=exoshell`
- `project=<normalized project directory basename>`
- `agent=<selected agent>`

The launcher will pass `--no-keep`, making the sandbox lifecycle follow the
coding agent's canonical process. The `sandbox_name` TOML setting and `--name`
launcher option will be removed. The runner will provide `--keep` for debugging
when a sandbox must remain after the agent exits.

## Consequences

- Concurrent launches do not require a launcher-managed name allocator.
- Sandboxes are deleted after their coding agent exits, including nonzero exits.
- Providers remain reusable and are not deleted with a sandbox.
- Launcher-created sandboxes can be selected using
  `openshell sandbox list --selector managed-by=exoshell`.
- Project and agent identity are available in labels and structured list output.
- The default sandbox-list table does not display labels; users must use a
  selector or structured output.
- Gateway-generated names are less memorable, and an extremely rare generated
  name collision can still cause creation to fail.
- Completed sandboxes are not retained for later restart or diagnosis unless
  the runner was started with `--keep`.
- OpenShell may retain provisioning-timeout records for diagnosis, even when
  `--no-keep` was requested.
- Detaching does not delete a sandbox while its coding agent remains alive.
- Multiple sandboxes using the same writable project directory can still
  conflict at the filesystem and Git levels; separate worktrees are recommended
  for concurrent editing.

## References

- [Launcher implementation](../scripts/exoshell_agent.py)
- [Launcher documentation](../README.md)
- [ADR-0016: Multi-agent launcher and ephemeral state](adr0016-multi-agent-launcher-and-ephemeral-state.md)
- [OpenShell sandbox management](https://docs.nvidia.com/openshell/sandboxes/manage-sandboxes)
