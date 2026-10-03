# Architecture

This repository assembles an OpenShell sandbox for multiple coding agents with
a portable filesystem layout and narrowly scoped, provider-backed credentials.

```text
OpenShell community image
          │
          ▼
 sandboxes/exoshell-base    pinned tools and non-secret defaults
          │
          ▼
 sandboxes/local-user       host UID/GID compatibility
          │
          ▼
 run-exoshell-agent.sh ──► scripts/exoshell_agent.py
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                 policies      providers     mounts/env
                    └─────────────┼─────────────┘
                                  ▼
                         selected coding agent
```

## Images and identity

`sandboxes/exoshell-base` keeps the community `sandbox` account, home `/sandbox`,
and OpenShell-managed OCI workdir. The source share is mounted at `/workspace`.
The machine-local final layer remaps `sandbox` to the host UID/GID so rootless
Podman can write bind-mounted files without embedding personal IDs in shared
sources.

## Launcher

The shell wrapper locates the repository and invokes the Python launcher. The
launcher validates TOML and CLI input, translates the host project below
`/workspace`, composes providers, and builds an argv-based `openshell sandbox
create` command. The selected executable is passed as a
positional argv value to `/usr/local/bin/exoshell-agent`, along with the
translated project path and unchanged agent arguments. The image executable
validates the directory under `/workspace`, changes into it, then replaces
itself with the selected agent. The project path is passed at launch because
OpenShell's create command does not select the main process's workdir.

For configured GitHub and GitLab hosts, the launcher injects the forge CLI host
selection and transient Git HTTPS authentication configuration. Provider
profiles still own credential injection and endpoint enforcement; a host setting
does not create or authorize a provider.

OpenShell generates each sandbox name. The launcher adds `managed-by`,
`project`, and `agent` labels for discovery and uses `--no-keep` so foreground
sandboxes are removed after the coding agent exits. `--keep` omits that flag
when a retained sandbox is needed for debugging.

## Policies and providers

Policies control filesystem, process, and network access. Provider profiles
bind placeholder credentials to selected binaries and inference endpoints.
Auxiliary agent traffic is auditable in policy, while inference endpoints are
enforced by provider profiles. Profiles allow unresolved placeholders in
inference bodies because conversations and tool output may contain opaque
placeholders belonging to other attached providers.

Provider profiles are backend-specific, not launcher-specific. OpenCode stays
backend-neutral: the chosen model/config determines whether its OpenAI,
Anthropic, or OpenRouter provider is used.

## Runtime state

Agent state remains in the sandbox container layer and is discarded when the
default `--no-keep` lifecycle removes the sandbox. `--keep` deliberately
retains that state for debugging. Codex uses image-owned configuration at
`/etc/codex`; OpenCode uses an image-provided global configuration from
`/sandbox/.config/opencode`, which project configuration can override. Optional
kubeconfig mounting is independent of agent selection. The launcher always
mounts `/tmp/gws` as tmpfs, including for providers attached later. The image
executable creates the private GWS credentials file and config directory when
all three GWS provider environment values are non-empty. It skips GWS when
none are non-empty and rejects a partial credential environment before starting
the agent. Provider changes require a fresh environment and helper invocation.
