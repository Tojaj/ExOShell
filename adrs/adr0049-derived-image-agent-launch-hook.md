---
status: accepted
date: 2026-11-26
topics:
  - launcher
  - sandbox-image
---

# 49. Let derived images customize agent launch

## Context

Derived images can ship client defaults at build time. An attached OpenShell
provider can supply instance-specific settings at sandbox startup. For example,
a provider can render an MCP endpoint URL into a non-secret file, and a client
that requires a literal URL needs that value before it starts.

A replacement launcher could read the file and configure the client, but would
duplicate the shared initialization established in ADR-0030. Adding the logic to
the base helper would couple it to a particular provider profile and client.

## Decision

We will support one optional executable at
`/usr/local/lib/exoshell/agent-launch`. After built-in initialization and entry
into the project directory, `exoshell-agent` will replace itself with the hook
as the sandbox user. It will pass the prepared environment and the exact client
argument vector, with the client executable as the hook's first argument.
Derived images will own the provider-specific and client-specific logic. The
hook can adjust the environment or arguments before executing the client.

## Consequences

- Images without the hook follow the existing launch path. Direct client
  invocations bypass the hook.
- The fixed path makes hook selection an image-level choice. The hook runs
  with the same prepared environment and sandbox privileges as the client.
- Valid symlinks work. An installed hook that cannot execute, including a
  dangling symlink, fails startup with a diagnostic that names the hook.
- Derived images need a base image containing the updated helper to use the
  hook.

## References

- [ExOShell issue #27](https://github.com/Tojaj/ExOShell/issues/27)
- [ADR-0030](adr0030-provider-controlled-agent-integrations.md)
- [Image startup helper](../sandboxes/exoshell-base/exoshell-agent)
- [Custom-image launch hook guide](../docs/customize/images.md#agent-launch-hook)
- [OpenShell provider-file implementation](https://github.com/NVIDIA/OpenShell/blob/main/crates/openshell-providers/src/profiles.rs)
