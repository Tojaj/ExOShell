---
status: accepted
date: 2026-10-25
topics:
  - sandbox-image
  - identity
  - podman
---

# 45. Allow explicit bounded local image identity

## Context

[ADR-0015](adr0015-host-uid-remap-not-keep-id.md) selected host numeric IDs
with bare `keep-id`. Some host IDs fall outside rootless Podman's subordinate
ID mapping, so image account remapping cannot represent them during a build.
Podman also supports mapping the host user to selected container IDs through
`keep-id:uid=...,gid=...`, independently of host file ownership.

## Decision

We will amend ADR-0015 by allowing `--uid UID` and `--gid GID` in the local-user
build, independently defaulting to `id -u` and `id -g`. We will accept decimal
IDs from 1 through 4294967294, rejecting root and the reserved u32 maximum
before invoking Podman. Operators selecting explicit IDs will configure the
gateway's `keep-id:uid=...,gid=...` to match the image. We will retain the thin
local identity layer and will not auto-detect namespace mappings or change
gateway configuration from the build script.

## Consequences

- Existing non-root defaults and base-image/tag options remain compatible.
- Explicit mapped IDs can avoid unmapped host IDs while shared files remain
  owned by the host user. Image IDs must still fit the available mapping.
- The gateway-wide mapping couples all its workload images to those IDs;
  operators must keep them aligned and verify writable shares locally.
- Policy continues to select the unprivileged `sandbox` account.

## References

- [Local identity build](../sandboxes/local-user/build.sh)
- [Local identity guide](../sandboxes/local-user/README.md)
- [Podman keep-id mapping](https://docs.podman.io/en/latest/markdown/podman-run.1.html#userns-mode)
- [OpenShell Podman driver configuration](https://docs.nvidia.com/openshell/reference/gateway-config)
