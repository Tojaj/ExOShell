---
status: accepted
date: 2026-09-18
author: Tomas Mlcoch
topics:
  - sandbox-image
---

# 11. Pin sandbox CLI versions in Dockerfile ARGs

## Context

The community OpenShell `base` image preinstalls agent CLIs (Claude Code,
OpenCode, Codex) and this repository's `exoshell-base` image layers extra tools on
top. Community `base` pins some npm packages in its own Dockerfile, but
Claude Code is installed with an unpinned `install.sh`, and a `:latest` base
tag still hides the exact versions that end up in a locally built image.

Three approaches were considered:

**Option A — float `@latest` / unpinned installers.** Always consume whatever
the registry or installer ships at build time. Versions are not visible in
git, two builds of the same commit can differ, and a compromised or
broken-on-arrival release is picked up immediately.

**Option B — inherit community `base` versions unchanged.** The extra tools in
`exoshell-base` would still be pinned, but the agents this setup actually runs
would lag on whatever the last `base` rebuild happened to contain (for
example OpenCode `1.2.18` while current releases are in the `1.18.x` line).

**Option C — pin every CLI this image cares about as a Dockerfile `ARG`.**
Bump the ARG and rebuild after reviewing the release. Overlay installs reuse
the community layout so OpenShell `binaries:` allowlists keep matching.

Agent install layouts have changed before: Claude Code's npm package is
deprecated (it would land under `/usr/lib/node_modules/@anthropic-ai/**`,
which provider profiles do not allow), and OpenCode's network process is a
native ELF under `/usr/lib/node_modules/opencode-ai/` (historically
`bin/.opencode`; current releases use `bin/opencode.exe`), not only the PATH
shim. A version bump is also the moment to confirm those paths.

## Decision

We will pin sandbox CLI versions in `ARG`s in
[`sandboxes/exoshell-base/Dockerfile`](../sandboxes/exoshell-base/Dockerfile) (Option C),
including Claude Code and OpenCode alongside the tools already pinned that
way (Codex, `gws`, `glab`, …).

Overlays will follow the community `base` install methods so policy paths
stay valid:

- OpenCode: `npm install -g opencode-ai@${OPENCODE_VERSION}` (same tree as
  `base`).
- Claude Code: native `install.sh` with a version argument, then copy to
  `/usr/local/bin/claude` (npm is not used).
- Native Claude auto-update is disabled via `DISABLE_AUTOUPDATER` and
  `DISABLE_UPDATES` so a writable home cannot undo the pin at runtime.

Floating `@latest` is not used. Being one or two releases behind current
latest is an allowed bump strategy when a new version has not been reviewed;
it is not a requirement to lag. Rebuild the image after each ARG bump.

## Consequences

**Positive:**

- The version of each agent CLI is visible in git (transparency).
- Builds of the same revision install the same CLIs (reproducibility; also
  noted in [ADR 0005](adr0005-custom-sandbox-image.md)).
- A deliberate bump is a cooling-off window against supply-chain incidents
  that ship as "latest".
- Each bump is a checkpoint that `/proc/<pid>/exe` still matches
  `binaries:` in the sandbox policy.

**Negative / constraints:**

- The image must be rebuilt to pick up a new CLI version.
- Claude's `install.sh` *script* is still fetched unpinned; only the version
  argument is pinned. `/usr` is read-only at runtime and `DISABLE_*` blocks
  the autoupdater as a backstop.
- Pins can go stale if ARGs are not reviewed when host or upstream CLIs
  move.

## References

- [`sandboxes/exoshell-base/Dockerfile`](../sandboxes/exoshell-base/Dockerfile)
- [`sandboxes/exoshell-base/README.md`](../sandboxes/exoshell-base/README.md)
- [`policies/policy.yaml`](../policies/policy.yaml)
- [ADR 0005](adr0005-custom-sandbox-image.md) — custom sandbox image
- [Claude Code native installer](https://code.claude.com/docs/en/setup)
