---
status: accepted
date: 2026-10-22
topics:
  - launcher
  - policy
---

# 44. Record the selected policy source on each sandbox

## Context

[ADR-0006](adr0006-policy-overlays-for-external-write-access.md) introduced
baseline reversion. Launcher configuration discovery later became independent
of the helper's checkout, as documented in
[ADR-0034](adr0034-launcher-config-discovery.md). Inferring a baseline from that
checkout can restore the wrong policy for a downstream or differently
configured sandbox. Requiring an explicit file every time avoids guessing but
discards information the launcher already knows.

OpenShell v0.1.5 exposes caller-owned annotations in sandbox creation and JSON
output. Labels cannot represent arbitrary absolute paths.

## Decision

We will record an explicitly selected policy's resolved absolute path in the
non-secret `exoshell.policy-source-file` annotation. `--no-policy` will omit it;
the explicit policy-selection requirement in ADR-0035 will remain.

Overlay `--revert` will use explicit `--base-file` first, otherwise this sandbox
annotation. Missing, malformed, or unavailable recorded sources will require
an explicit file. We will remove checkout configuration and public-policy
fallbacks. Ordinary overlay application and explicit baselines will not fetch
sandbox metadata.

## Consequences

- Reversion follows the selected sandbox across caller directories and works
  with customization repositories through the existing public launcher.
- The path identifies a source file, not a snapshot. Revert reads its current
  network entries while preserving live static policy sections.
- Older, direct, or `--no-policy` launches need `--base-file`. So do moved files
  or clients on another host without access to the recorded path.
- No generic arbitrary-annotation launcher option or local tracking store is
  required. Annotation values expose non-secret paths in sandbox metadata.

## References

- [OpenShell issue #4303](https://github.com/NVIDIA/OpenShell/issues/4303)
- [OpenShell PR #4325](https://github.com/NVIDIA/OpenShell/pull/4325)
- [v0.1.5 sandbox JSON formatting](https://github.com/NVIDIA/OpenShell/blob/v0.1.5/crates/openshell-cli/src/run.rs)
