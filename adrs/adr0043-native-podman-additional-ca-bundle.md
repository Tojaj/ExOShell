---
status: accepted
date: 2026-10-22
topics:
  - podman
  - supervisor
  - tls
---

# 43. Configure private Podman CA trust through the gateway

## Context

[ADR-0026](adr0026-custom-podman-supervisor-ca-bundle.md) required a custom
supervisor image because workload-image roots did not reach the separate
Podman supervisor. That image needed rebuilding for each OpenShell upgrade
and CA rotation, and replaced the supervisor's entire system bundle.

OpenShell v0.1.5 adds `additional_ca_bundle` for direct inspected egress,
independently of a corporate forward proxy. Keeping the custom image as a
fallback would retain unnecessary version coupling.

## Decision

We will configure an operator-owned, gateway-readable host PEM through
`[openshell.drivers.podman] additional_ca_bundle` and use the stock supervisor
matching the installed OpenShell version. We will remove CA-only custom
supervisor builds and their image overrides. Organization-specific certificate
sources and paths will remain in customization repositories or local setup.

We will retain workload-image CA installation for build-time clients and tools
that use the image's trust store. Gateway changes and CA rotation will require
a restart and fresh sandboxes.

## Consequences

- Additional roots augment public roots in the supervisor and injected workload
  bundle without rebuilding the supervisor image.
- The PEM must exist on the gateway host. Invalid or unreadable material can
  prevent gateway startup, so stage it before changing the configuration.
- Trust applies to every Podman sandbox and destination on the gateway; network
  policy and credential bindings still govern access.
- `proxy_ca_bundle` remains the separate forward-proxy option.

## References

- [OpenShell PR #3996, fixing #3781](https://github.com/NVIDIA/OpenShell/pull/3996)
- [v0.1.5 Podman configuration and validation](https://github.com/NVIDIA/OpenShell/blob/v0.1.5/crates/openshell-driver-podman/src/config.rs)
- [v0.1.5 gateway configuration](https://github.com/NVIDIA/OpenShell/blob/v0.1.5/docs/how-it-works/gateways/configuration.mdx)
