# ExOShell specification

Status: implemented baseline. This document describes the generic project;
README.md covers setup and CUSTOMIZATION.md covers site-specific extensions.

## 1. Purpose and security goals

Run Codex, Claude Code, or OpenCode against a selected local source tree in
NVIDIA OpenShell sandboxes using rootless Podman. Scope host filesystem access,
keep long-lived credentials behind provider placeholders where supported,
and discard agent runtime state when a normal session ends.

Provider placeholders are rewritten by OpenShell for permitted HTTPS requests.
They do not hide credentials supplied through a mounted kubeconfig or returned
by an interactive login. General traffic in the baseline is audited; provider
endpoints enforce their credential and request boundaries.

## 2. Images and gateway

The generic workload image extends the OpenShell community base with pinned
agent CLIs and supporting tools. A machine-local ownership layer remaps its
`sandbox` user to the host UID/GID. No host-specific numeric identity is committed.
`build.sh` builds both layers regardless of the caller's working directory.

The Podman gateway must enable bind mounts and caller-supplied driver config.
The documented setup disables resource admission and uses `userns = "keep-id"`;
operators must trust gateway users to select host paths. See README.md and
ADR-0025. Private trust roots and extra client defaults belong in derived images.
On OpenShell 0.1.2, inspected egress uses a separate supervisor container;
CUSTOMIZATION.md and ADR-0026 document its trust configuration.

## 3. Launcher and filesystem

`run-exoshell-agent.sh` delegates to the Python launcher. Python 3.11 or newer
is required. The CLI accepts the selected agent, image, provider instances,
policy, optional integrations, configuration file, and host project directory.
Arguments after `--` are forwarded unchanged to the agent.

The selected project defaults to the caller's current directory. With no
`host_share`, it is mounted at `/workspace`. With a larger share, the project
must be beneath that share and retains its relative path below `/workspace`.
Paths are resolved before launch, including symlinks. The image entry point
validates the container project path and starts the agent there.

The launcher injects the selected project's effective Git name and email.
Configured forge hosts select the CLI host, HTTPS URL rewriting, and transient
Git credential helpers. They do not grant network access or create providers.

Configuration defaults come from the ignored `.exoshell.local.toml` beside the
launcher or an explicit `--config` file. File paths in TOML resolve relative
to that configuration file. CLI paths resolve relative to the caller's working
directory. CLI settings override configuration. Common and selected-agent
providers compose; explicit CLI provider options replace the combined list.

## 4. Policies and providers

`policies/policy.yaml` is the portable baseline. Select it with the launcher's
`--policy` option or the configuration `policy` setting. Without a selected
policy, the launcher leaves policy selection to OpenShell.

Providers define credential bindings and endpoint rules independently of
filesystem grants. Import and create only the providers needed for a session;
providers.md documents the supported profiles. Avoid attaching profiles with
conflicting credential environment variables.

GitHub and GitLab GraphQL endpoints are declared once per host in user policy,
allowing network overlays to replace an entry when enabling writes. Provider
profiles retain credential bindings and REST/Git transport rules. Overlay
composition replaces each named network policy entry in full and preserves
live static policy sections. Reversion restores network entries from the
selected baseline. PyYAML is required by `policy-overlays/apply.py`.

## 5. Optional integrations and lifecycle

A kubeconfig can be mounted read-only; its credentials remain readable inside
the sandbox. Google Workspace initialization instead writes provider-backed
placeholders to a private credentials file in tmpfs. Public package registries
and Atlassian MCP access are opt-in provider integrations.

Atlassian MCP defaults to disabled. At agent startup, the image helper enables
the built-in entry only when the provider-backed `ATLASSIAN_MCP_BEARER_TOKEN`
environment value is non-empty. It overrides conflicting entry enablement for
Codex, Claude Code, and OpenCode while preserving unrelated configuration.
Claude user state is kept inside `/sandbox/.claude` through `CLAUDE_CONFIG_DIR`.
Provider changes require a fresh process environment and another helper
invocation; bare client commands bypass this startup decision.

OpenShell assigns sandbox names. The launcher adds `managed-by=exoshell`,
project, and agent labels and passes `--no-keep` by default. Agent state lives
in the container layer and is discarded at deletion; project files remain on
the host. `--keep` retains a sandbox for diagnosis and requires later cleanup.

## 6. Customization and validation

Maintain organization-specific provider profiles, policies, image layers,
and model choices in a separate repository. Use an explicit upstream checkout
path and existing CLI/configuration interfaces; no organization-specific
launcher logic is required. See ADR-0027.

Run `python3 -m unittest discover -s tests -v` and the version-check skill tests.
Lint profiles and policies using the installed OpenShell CLI. On a capable
host, build the images and perform the identity, filesystem, inference, forge,
and lifecycle smoke checks described in README.md and CUSTOMIZATION.md.
