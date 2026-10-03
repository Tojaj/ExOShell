---
status: superseded
superseded-by: adr0030-provider-controlled-agent-integrations.md
date: 2026-09-27
author: Tomas Mlcoch
topics:
  - launcher
  - sandbox-image
---

# 23. Put shared startup behavior in an ExOShell image executable

Superseded by [ADR-0030](adr0030-provider-controlled-agent-integrations.md),
which preserves the image executable contract and replaces explicit GWS opt-in
with provider-controlled initialization.

## Context

The host launcher selects a project, agent, providers, policy, and mounts for
each sandbox. It previously constructed an inline shell command to change into
the selected project and perform optional runtime setup before starting the
agent. OpenShell accepts a trailing command as the sandbox main process and
documents `--workdir` for `sandbox exec`, but the create command does not
select that process's project directory.

Keeping startup commands in the host launcher avoids an image rebuild. A
public image executable instead gives direct OpenShell users the same startup
behavior and a place for future setup shared across agents and use cases. It
adds a component that must be maintained and rebuilt with the image.

## Decision

We will provide `/usr/local/bin/exoshell-agent` in the generic image. It will
accept `PROJECT -- COMMAND [ARG ...]`, validate the project directory below
`/workspace`, perform requested runtime setup, change directory, and replace
itself with the command. It will not select an agent or infer integrations from
attached providers. Optional setup will require an explicit opt-in and fail
before starting the command if required inputs are absent.

The host launcher will continue selecting the agent, providers, policy,
mounts, Git identity, and host-to-sandbox project path. The image executable
can support other shared startup tasks later without making them requirements
for ordinary agent startup or direct OpenShell use.

## Consequences

- Direct OpenShell users can invoke the same startup behavior as the launcher,
  provided they supply the required project mount and any opted-in integrations.
- The host launcher no longer constructs shell source for its main process.
- The generic image gains a small runtime component and must be rebuilt to
  change it.
- GWS initialization is the first optional task: it requires `EXOSHELL_GWS=1`,
  provider environment values, and writable private runtime storage. A
  provider attachment alone does not request it.
- Git configuration generation, other provider-specific setup, and host-side
  decisions remain separate choices.

[ADR-0028](adr0028-provider-controlled-atlassian-mcp.md) adds a narrow exception
to explicit opt-in: the image helper infers Atlassian MCP enablement from its
provider credential placeholder. GWS still requires its explicit opt-in.

## References

- [Image executable](../sandboxes/exoshell-base/exoshell-agent)
- [Host launcher](../scripts/exoshell_agent.py)
- [GWS placeholder decision](adr0002-gws-credentials-via-provider-body-rewrite.md)
- [Multi-agent launcher decision](adr0016-multi-agent-launcher-and-ephemeral-state.md)
- [Sandbox lifecycle decision](adr0019-sandbox-lifecycle-for-agent-state.md)
- [OpenShell sandbox creation and execution](https://docs.nvidia.com/openshell/sandboxes/manage-sandboxes)
