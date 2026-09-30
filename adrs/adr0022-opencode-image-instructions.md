---
status: accepted
date: 2026-09-25
author: Tomas Mlcoch
topics:
  - sandbox-image
  - opencode
---

# 22. Bake operational instructions into the OpenCode image

## Context

Some sandbox problems require host-side remediation that an agent cannot
perform from inside the sandbox. For example, a file moved into a running
SELinux-labeled bind mount can retain a host label and become inaccessible to
the sandbox. Project instructions are not a reliable place for this knowledge:
the problem is caused by the host and the guidance should apply to every
project using the image.

OpenCode supports an `instructions` configuration option containing explicit
files and glob patterns. The image already provides global OpenCode
configuration at `/sandbox/.config/opencode/opencode.json`.

## Decision

We will bake short, independent operational instruction files into the generic
base image and list them explicitly in the image-provided OpenCode
configuration. Each recurring sandbox-specific problem will get its own file.
Instruction files will describe symptoms, identify the likely boundary between
host and sandbox, and give the user a safe host-side remediation when needed.

## Consequences

- Agents can recognize documented sandbox-specific failures and give actionable
  guidance without project-specific configuration.
- Instruction files remain small and discoverable instead of becoming one large
  general-purpose prompt.
- Adding or changing an instruction requires rebuilding the image.
- The instruction list is global configuration and can be overridden by later
  OpenCode configuration layers.
- Instructions must not contain credentials, host-specific paths, or commands
  that pretend the agent can modify the host.

## References

- [Base OpenCode configuration](../sandboxes/exoshell-base/opencode.json)
- [Base image Dockerfile](../sandboxes/exoshell-base/Dockerfile)
- [OpenCode configuration instructions](https://opencode.ai/docs/config/#instructions)
