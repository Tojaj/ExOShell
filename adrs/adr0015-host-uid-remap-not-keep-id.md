---
status: accepted
date: 2026-09-19
author: Tomas Mlcoch
topics:
  - sandbox-image
  - identity
---

# 15. Remap `sandbox` to the host UID; do not treat `keep-id` as ownership

## Context

Writable host shares need two independent settings in the Podman gateway:

- `enable_bind_mounts = true` allows a host path to appear in the sandbox.
- `userns = "keep-id"` (no `uid=` / `gid=`) keeps the host user's **numeric**
  UID and GID inside the container.

Neither maps the host account onto the image user. Community `base` runs as
`sandbox` with a system UID (currently 998). A host share owned by 1001 is
still owned by 1001 under bare `keep-id`. A process running as 998 cannot
write it.

Parameterized `userns = "keep-id:uid=998,gid=998"` would map the host user
onto that image UID and could make a generic image writable. It is
gateway-global, must track the community UID if it changes, and has not been
verified as the portable default.

[ADR-0014](adr0014-portable-launcher-and-image-identity.md) already chose a
thin local image layer (RF-10) so shared sources contain no host username or
personal IDs.

## Decision

We will keep remapping community `sandbox` to the current host UID and GID in
the local-only image. Gateway `enable_bind_mounts` and bare `keep-id` remain
required for the mount and for numeric identity not to be scrambled; they do
not replace that remap.

We will not switch to `keep-id:uid=<image-uid>` until that mapping is verified
to give writable shares without a local image for the supported OpenShell and
Podman versions.

## Consequences

- Every machine still builds `sandboxes/local-user` with `id -u` / `id -g`.
- The local build must free a colliding distro identity (Ubuntu Noble's
  `ubuntu` is 1000:1000) before `usermod`.
- Policy stays `run_as_user: sandbox`; only the numeric IDs change.
- Revisit this ADR if parameterized `keep-id` is confirmed to replace the
  local identity layer.

## References

- [Local identity layer](../sandboxes/local-user/Dockerfile)
- [ADR-0014](adr0014-portable-launcher-and-image-identity.md)
- [OpenShell Podman driver `userns`](https://docs.nvidia.com/openshell/reference/gateway-config)
