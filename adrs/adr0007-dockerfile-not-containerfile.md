---
status: deprecated
date: 2026-09-14
author: Tomas Mlcoch
topics:
  - sandbox-image
---

# 7. Name the sandbox build file `Dockerfile`, not `Containerfile`

OpenShell 0.1.0 removed directory and Dockerfile builds from `sandbox create
--from`; this decision no longer constrains the filename. The build-and-tag
workflow uses `podman build` before passing an image reference to OpenShell.
The following context and consequences describe the earlier CLI behavior.

## Context

Podman and Buildah accept both `Dockerfile` and `Containerfile` as the default build-instruction filename. The Fedora ecosystem has generally converged on `Containerfile` as the preferred name; renaming away from it imposes a minor friction on contributors familiar with that convention.

OpenShell's `sandbox create --from` implementation has two bugs that make `Containerfile` unusable today:

1. **Directory lookup only finds `Dockerfile`.** When a directory is passed to `--from`, the CLI looks for `Dockerfile` exclusively; a `Containerfile` in the same directory is silently ignored with the error `No Dockerfile found in directory`.  
   (Upstream: [#2420](https://github.com/NVIDIA/OpenShell/issues/2420) — open, stale)

2. **Direct file path to `Containerfile` is rejected.** When a path like `sandboxes/exoshell-base/Containerfile` is passed directly, the CLI reports `local --from path is not a regular file or directory`, even though the file is a valid UTF-8 text file.
   (Upstream: [#2420](https://github.com/NVIDIA/OpenShell/issues/2420) — same issue)

Both upstream issues are open and currently stale. The proposed fix in #2420 goes further than just adding `Containerfile` recognition — it proposes removing all hardcoded filename restrictions so any valid build-instruction file is accepted regardless of name — but no timeline for a fix is indicated.

## Decision

We will name the sandbox build-instruction file `Dockerfile` (`sandboxes/exoshell-base/Dockerfile`) until upstream fixes both bugs.

## Consequences

**Positive:**
- On the earlier CLI, `openshell sandbox create --from sandboxes/exoshell-base/` worked without error.
- No workarounds, wrappers, or symlinks needed.

**Negative / constraints:**
- Diverges from Fedora/Podman convention of naming the file `Containerfile`.
- OpenShell 0.1.0 removed the directory-build behavior; Podman accepts either filename when building the image separately.

## References

- [OpenShell issue #2420](https://github.com/NVIDIA/OpenShell/issues/2420) — add support for `Containerfile`-named files
- [OpenShell issue #2779](https://github.com/NVIDIA/OpenShell/issues/2779) — build through selected runtime (Podman support)
- [OpenShell 0.1.0 upgrade guide](https://docs.nvidia.com/openshell/upgrade/0-1-0)
- [`sandboxes/exoshell-base/`](../sandboxes/exoshell-base/) — image definition directory
- [`adr0005-custom-sandbox-image.md`](./adr0005-custom-sandbox-image.md) — why a custom image is used
