---
status: accepted
date: 2026-09-30
topics:
  - customization
  - repositories
---

# 27. Keep site-specific customization in a separate repository

## Context

Provider profiles, policies, and image layers may reveal private infrastructure.
Maintaining them alongside portable sources complicates publication and duplicates
shared code. The launcher already accepts an external configuration file and
policy path, and the overlay helper accepts explicit overlay and baseline paths.

## Decision

We will maintain portable sources here and site-specific configuration in a
separate repository. Customizations will consume an explicitly selected upstream
checkout and build derived images from its generic workload image. They will use
existing OpenShell and ExOShell interfaces rather than fork the launcher.

## Consequences

- Customization repositories can preserve their own history and access controls.
- Upstream updates require compatibility checks against the selected customization.
- Configuration paths resolve relative to the external TOML file; overlay paths
  and `--base-file` must be explicit when they belong to another repository.
- Keep model choices and private infrastructure inventories outside shared sources.

## References

- [Separate customization repository](../CUSTOMIZATION.md#separate-customization-repository)
- [Launcher](../scripts/exoshell_agent.py)
- [Policy overlays](../policy-overlays/README.md)
- [OpenShell provider profiles](https://docs.nvidia.com/openshell/sandboxes/providers-v2)
