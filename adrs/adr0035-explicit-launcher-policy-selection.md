---
status: accepted
date: 2026-10-07
topics:
  - launcher
  - policy
---

# 35. Require a selected launcher policy with an explicit opt-out

## Context

Launching without a selected policy has been reported to stall provisioning
with an effective-configuration activation error. The exact failure is not
confirmed. Omitting OpenShell's `--policy` does not guarantee its restrictive
default: an environment or image policy can supply another policy. ExOShell
inherits a policy from the community base image.

Automatically selecting a checkout policy or generating a fallback would
introduce default-policy behavior before an installer and its policy locations
are defined.

## Decision

We will require a policy selected through CLI or configuration unless the user
explicitly supplies `--no-policy`. Missing selection will fail before image
checks, Git identity lookup, or sandbox creation, with instructions for choosing
a policy or explicitly delegating selection to OpenShell.

We will retain regular-file existence checks for selected policy paths and
CLI precedence over configuration. `--no-policy` will clear the configured
path and omit OpenShell's policy argument. OpenShell will remain responsible
for validating policy content. Automatic fallback and installed-policy lookup
will be deferred.

## Consequences

- Existing launches that omit policy selection must configure a policy, pass
  `--policy`, or deliberately opt out with `--no-policy`.
- Accidental omission cannot silently select an inherited image policy.
- Explicit delegation can still encounter OpenShell activation failures.
- Policy selection does not require image changes or a rebuild.

## References

- [OpenShell default policy](https://docs.nvidia.com/openshell/how-it-works/policies/default-policy)
- [Community base image Dockerfile](https://github.com/NVIDIA/OpenShell-Community/blob/main/sandboxes/base/Dockerfile)
- [OpenShell policy loading and defaults](https://github.com/NVIDIA/OpenShell/blob/main/crates/openshell-policy/src/lib.rs)
- [Launcher](../scripts/exoshell_agent.py)
- [ADR-0034](adr0034-launcher-config-discovery.md)
