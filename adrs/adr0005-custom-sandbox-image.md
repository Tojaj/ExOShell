---
status: superseded
date: 2026-09-11
author: Tomas Mlcoch
superseded-by: adr0014-portable-launcher-and-image-identity.md
topics:
  - sandbox-image
---

# 5. Build a custom sandbox image instead of bind-mounting host binaries

Superseded by [ADR-0014](adr0014-portable-launcher-and-image-identity.md).

## Context

The default OpenShell sandbox image (`ghcr.io/nvidia/openshell-community/sandboxes/base`) ships common agent CLIs (Codex, Claude Code, OpenCode, git, gh, node, curl) but lacks the host tools this setup depends on: `gws`, `oc`/`kubectl`, `glab`, `uv`/`uvx`, `rg`, `pre-commit`, `oras`, `yq`, and `tkn`. It also runs as the container's default user, so `~` and `/etc/passwd` may not match the host user.

Three approaches were considered:

**Option A — bind-mount host binaries into the sandbox.** Mount each tool's binary (and its transitive dependencies) from the host filesystem. This is fragile: `gws` is a Node script that needs the entire `@googleworkspace/cli` package tree under `/usr/local/lib/node_modules/`; `oc`/`kubectl` pull in shared libraries that may not exist in the Debian-based sandbox; and `/proc/<pid>/exe` resolves to the kernel-level target (e.g., `node` for `gws`), not the wrapper script. Each tool's dependency tree must be traced and mounted individually, and any host library update can silently break the sandbox.

**Option B — install tools at sandbox start via an init script.** Run `npm install -g @googleworkspace/cli`, download `oc`, etc. in a startup script before the agent launches. This adds minutes of network-dependent setup to every sandbox creation, makes cold starts unreliable (registry outages, rate limits), and produces non-reproducible environments.

**Option C — build a custom OCI image layered on top of `base`.** A Dockerfile in this repository (`sandboxes/exoshell-base/`) extends the community `base` image, installs the required tools at known paths, and creates a non-root user with the host UID/GID. The image is built once and reused across sandbox invocations.

A secondary concern is username fidelity. SPEC D1 chose the simplest approach — the default container user — and achieved *path* fidelity by mounting the host source directory at the corresponding container path. But `id -un` inside the sandbox does not return the host username, and `~` does not expand to the host user's home directory. A custom image resolves this by creating the user with the correct UID/GID and home directory.

## Decision

We will build a custom sandbox image (Option C), defined by a Dockerfile in `sandboxes/exoshell-base/`, extending the community `base` image.

The image will:

1. Install the tools the agents need (`gws`, `oc`, `kubectl`, `glab`, `uv`/`uvx`, `rg`, `pre-commit`, `oras`, `yq`, `tkn`) at the paths listed in `policy.yaml`.
2. Create a non-root user with the host UID/GID and matching home directory.
3. Bake no secrets — tokens, kubeconfigs, and OAuth credentials remain on the host, bind-mounted at create time.

This is the only approach that gives a reproducible, fast-starting sandbox with all required binaries at predictable paths, matching the policy's `binaries:` allowlist.

## Consequences

**Positive:**
- Sandbox creation is fast — no network fetches or install steps at start time.
- Environment is reproducible and version-pinned in the Dockerfile.
- Username and home directory match the host, eliminating path mismatches.
- Policy `binaries:` paths resolve correctly without per-tool bind-mount gymnastics.

**Negative / constraints:**
- The image must be rebuilt when upstream tool versions change (e.g., new `oc` release). A rebuild note in the Dockerfile will track this.
- The Dockerfile encodes one user's UID/GID, making it personal infrastructure rather than team-shareable without parameterization.
- Must comply with OpenShell BYOC rules: standard Linux image, non-root user, `iproute2` installed, writable workspace directory.

## References

- [`sandboxes/exoshell-base/`](../sandboxes/exoshell-base/) — image definition directory
- [`policy.yaml`](../policies/policy.yaml) — portable sandbox policy with `binaries:` allowlist
- [`SPEC.md`](../SPEC.md) — current generic image and ownership requirements
