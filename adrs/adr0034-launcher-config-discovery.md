---
status: accepted
date: 2026-10-07
topics:
  - launcher
  - customization
---

# 34. Discover one launcher configuration from the caller and standard locations

## Context

[ADR-0014](adr0014-portable-launcher-and-image-identity.md) introduced local
TOML defaults, and [ADR-0027](adr0027-separate-customization-repository.md)
established separate customization repositories. Automatic lookup beside the
launcher couples machine defaults to an upstream checkout and makes invocation
from a customization repository surprising. User and system locations support
defaults across projects. Merging several files would make omitted settings
depend on configuration outside the selected file.

## Decision

We will load exactly one configuration: explicit `--config PATH`, otherwise
the first existing file among the caller's `.exoshell.local.toml`,
`$XDG_CONFIG_HOME/exoshell/exoshell.local.toml`, and
`/etc/exoshell/exoshell.local.toml`. Following XDG guidance, unset, empty, or
relative `XDG_CONFIG_HOME` will use `~/.config`. Explicit paths will accept
any filename, resolve relative to the caller, and bypass discovery.

We will use built-in defaults for omitted keys and when no file is found.
Invalid, unreadable, and non-file candidates will fail rather than fall
through. CLI overrides, provider composition, and config-relative paths will
retain their existing behavior. We will omit launcher-directory, positional
project, parent-directory, uppercase-alias, and `XDG_CONFIG_DIRS` searches.
We will leave policy-overlay baseline discovery unchanged.

## Consequences

- A caller can choose per-directory defaults or user defaults across projects.
- Empty and partial files deliberately prevent lower-priority inheritance.
- Checkout configs remain discoverable when running from that checkout.
  Callers elsewhere must pass `--config` or move the file to the user directory
  and adjust relative paths.
- Overlay users must supply the correct `--base-file` explicitly; launcher
  discovery does not determine that helper's baseline.

## References

- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/)
- [Launcher](../scripts/exoshell_agent.py)
- [Customization guidance](../CUSTOMIZATION.md)
- [ADR-0016: multi-agent launcher](adr0016-multi-agent-launcher-and-ephemeral-state.md)
