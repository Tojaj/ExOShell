---
status: accepted
date: 2026-09-28
topics:
  - podman
  - supervisor
  - tls
---

# 26. Supply private upstream CA trust through a custom Podman supervisor image

## Context

Since OpenShell 0.1.2, Podman runs the workload and its network supervisor in
separate containers. The supervisor establishes inspected upstream HTTPS
connections and reads CA certificates from its own image. A private root in the
workload image therefore no longer lets the supervisor verify a service signed
by that root. The resulting connection is allowed by policy but fails before an
HTTP response. The previous single-container arrangement used the workload's
trust store; [upstream issue #3781](https://github.com/NVIDIA/OpenShell/issues/3781)
records the regression and the confirmed cause.

Podman's `proxy_ca_bundle` requires `https_proxy`, so it does not configure CA
trust for direct egress. Mounts supplied to the workload do not reach the
supervisor. Setting `tls: skip` avoids upstream verification but also loses HTTP
inspection and credential rewriting. An operator-managed CA bundle for direct
egress has been requested upstream, but is unavailable in the affected release.

## Decision

We will build an operator-specific supervisor image from the official
supervisor image for the installed OpenShell version, replacing its system CA
bundle with a bundle that includes the required private roots and public roots.
We will select that image using the Podman gateway's `supervisor_image` setting,
restart the gateway, and create fresh sandboxes. Workload clients that also
connect directly to private-CA services will receive their own CA bundle.

We will keep this trust configuration in the image and gateway setup, without
adding CA handling to the sandbox launcher or relaxing TLS policy. We will
revisit the custom image when OpenShell supports an operator-owned additional
upstream CA bundle for direct, inspected egress.

## Consequences

- Inspected requests to private-CA services can complete with certificate and
  hostname verification enabled; public-CA services remain trusted when the
  copied bundle includes their roots.
- `supervisor_image` applies to all Podman sandboxes on the gateway. Every
  supervisor receives the added trust anchors, although network policy still
  controls which destinations each sandbox may contact.
- The supervisor image must be rebuilt for OpenShell upgrades and CA rotations.
  Its base image must match the installed OpenShell release.
- Copying a whole system bundle also replaces the official image's system
  bundle, so the source bundle must retain the public roots the deployment needs.

## References

- [OpenShell issue #3781: Podman upstream CA regression](https://github.com/NVIDIA/OpenShell/issues/3781)
- [OpenShell Podman supervisor container selection in v0.1.2](https://github.com/NVIDIA/OpenShell/blob/v0.1.2/crates/openshell-driver-podman/src/container.rs#L1588-L1593)
- [OpenShell upstream TLS root-store construction in v0.1.2](https://github.com/NVIDIA/OpenShell/blob/v0.1.2/crates/openshell-supervisor-network/src/l7/tls.rs#L272-L318)
