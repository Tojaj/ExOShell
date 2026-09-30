---
status: accepted
date: 2026-09-28
topics:
  - sandbox-mounts
  - gateway
---

# 25. Opt out of Podman resource admission for host bind mounts

## Context

ExOShell's launcher mounts a selected gateway-host project at `/workspace` via
Podman `driver_config`. OpenShell 0.1.0 disables caller-supplied driver config
by default and rejects raw host binds while resource admission is enabled:
host paths cannot be approved with the resource labels used for engine volumes.
An operator-controlled static mount or labeled volume would change the
per-project host-share workflow, and is not used by this launcher.

## Decision

We will require `allow_driver_config = true`, `enable_bind_mounts = true`, and
`resource_admission.enabled = false` under the Podman driver in the local
gateway's schema-v2 configuration. The launcher will continue to select the
host path at sandbox creation, without embedding host-specific paths in shared
configuration. This is an operator opt-in, not a setting the launcher changes.

## Consequences

Users who can create sandboxes on this gateway can choose host paths in driver
config. Use this setup only on a gateway whose users are trusted to do so;
ExOShell's project-path checks limit its own launcher, not other callers.
Other OpenShell mount validation remains in effect. Revisit this decision if
OpenShell provides a way to approve per-project host binds without disabling
resource admission for the selected driver.

## References

- [OpenShell external resource admission](https://docs.nvidia.com/openshell/how-it-works/gateways/configuration#external-resource-admission)
- [OpenShell Podman mounts](https://docs.nvidia.com/openshell/how-it-works/sandboxes/runtimes#podman-mounts)
- [ADR-0015](adr0015-host-uid-remap-not-keep-id.md)
