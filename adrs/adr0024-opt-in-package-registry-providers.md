---
status: accepted
date: 2026-09-28
topics:
  - providers
  - network-policy
---

# 24. Select package registry access per sandbox with providers

## Context

Agents and package managers need registry access to inspect and install
dependencies. The existing baseline policy audited PyPI hosts, making Python
downloads available without a project choosing them. We considered baseline
grants (simple, but implicit and broad) and policy overlays (selectable, but
requiring a separate policy file for each combination). Independent OpenShell
providers are already composable with the launcher's agent providers and with
direct sandbox creation.

## Decision

We will provide credential-free, policy-only profiles for npm, PyPI, Go modules,
and Cargo, attached only when selected for a sandbox. We will remove PyPI from
the baseline policies. Each profile will enumerate official registry hosts,
allowed client binaries, and read methods; npm will also allow only its two
audit POST paths. Users can clone profiles with distinct IDs for enterprise
proxies, mirrors, or private registries and configure their package managers to
use those endpoints.

## Consequences

- Registry selection is explicit, independently composable, and auditable;
  dependencies cannot silently rely on public registry access from the baseline.
- A grant enables network access, not publishing. Authentication for private
  registries requires a separate suitable credential binding.
- Existing uvx/pip fetches, including MCP installs, need the Python provider.
  Go and Cargo also need an image that supplies those tools.
- A private clone does not itself grant public registry access, but another
  attached provider or the effective policy might. Client configuration and
  secondary hosts must be reviewed per installation.

## References

- [Upstream credential-free PyPI example](https://github.com/NVIDIA/OpenShell/blob/main/providers/pypi.yaml)
- [OpenShell Providers v2](https://docs.nvidia.com/openshell/sandboxes/providers-v2)
- [ExOShell provider setup](../providers.md)
- [ExOShell baseline policy](../policies/policy.yaml)
- [ExOShell policy overlays](../policy-overlays/README.md)
