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

Shared operational guidance lives in the base image's `agent-instructions/`
and is installed under `/etc/exoshell/instructions/`. The build combines the
Markdown files in filename order into Codex's `developer_instructions` in
`/etc/codex/config.toml` and Claude's managed `/etc/claude-code/CLAUDE.md`.
OpenCode's global configuration lists the individual installed files. This
guidance applies to direct agent launches and requires an image rebuild to
change. Higher-precedence Codex configuration can replace the combined value;
Claude managed memory is behavioral guidance rather than enforcement. See
ADR-0032 and CUSTOMIZATION.md for derived-image regeneration.

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

The CLI-only `--no-share` option starts the agent in the image's writable
`/workspace` without launcher-supplied host bind mounts. It clears configured
`host_share` and `kubeconfig` paths before checking their existence and rejects
explicit `--host-share`, `--kubeconfig`, or positional project arguments.
The host project and share are absent; configuration discovery, policy selection,
providers, and the `/tmp/gws` tmpfs still apply. OpenShell manages its own
internal storage. See ADR-0037.

The launcher injects the selected project's effective Git name and email.
With `--no-share`, it reads only global host Git configuration and injects
identity when both name and email are present. Missing or partial identity
does not block launch; users can configure Git inside the sandbox. Other Git
configuration read failures are errors.
Configured forge hosts select the CLI host, HTTPS URL rewriting, and transient
Git credential helpers. They do not grant network access or create providers.

Configuration loads exactly one file, in priority order: explicit `--config
PATH`, `.exoshell.local.toml` in the caller's current directory,
`$XDG_CONFIG_HOME/exoshell/exoshell.local.toml`, then
`/etc/exoshell/exoshell.local.toml`. An unset, empty, or relative
`XDG_CONFIG_HOME` uses `~/.config`. Explicit config accepts any filename,
resolves relative to the caller's directory, and bypasses discovery.
Absent candidates are skipped; invalid, unreadable, or non-file candidates
and missing explicit files are errors. With no file, built-in defaults apply.
Missing keys in a selected file also use built-in defaults, without inheriting
from lower-priority files.

File paths in TOML resolve relative to the selected configuration file. CLI
paths resolve relative to the caller's working directory. CLI settings
override configuration. Common and selected-agent providers compose; explicit
CLI provider options replace the combined list. Discovery does not search the
launcher directory, positional project, parents, uppercase aliases, or
`XDG_CONFIG_DIRS`. A checkout config is still discovered when called from
that checkout; callers elsewhere must use `--config` or move it to the user
directory. Overlay users must supply the correct `--base-file` explicitly;
launcher discovery does not determine the helper's baseline. See ADR-0034.

Each agent table also accepts optional non-empty `model` and `effort` strings.
Only the selected agent's values apply; omitted fields retain native defaults.
The launcher accepts `--model` and `--effort` overrides and mutually exclusive
`--no-model` and `--no-effort` options to suppress the respective ExOShell
setting. Native model/effort options after `--` take precedence and forwarded
arguments remain unchanged. ExOShell validates string values but delegates
model availability and effort-level compatibility to the selected agent.

Codex receives TOML-quoted `model` and `model_reasoning_effort` CLI config
overrides. Claude receives native `--model` and `--effort` options. OpenCode
uses native model selection; effort requires an explicit effective model.
Interactive OpenCode startup merges that pair into the built-in `build` and
`plan` agent entries in `OPENCODE_CONFIG_CONTENT`, preserving unrelated
configuration and MCP state. Custom agents retain their own variants.
`opencode run` receives `--variant` instead. These are starting selections
that users can change during a session. See ADR-0036 and CUSTOMIZATION.md.

The CLI-only `-v` / `--verbose` flag reports the absolute selected configuration
path before loading it, or identifies built-in defaults when no file is selected.
After successful settings validation, it reports every effective launcher setting,
including CLI overrides, composed providers, and resolved project and mount paths.
The `no_share` diagnostic reports the sharing opt-out; suppressed host project,
share, and kubeconfig paths are `null`.
Diagnostics use `exoshell: key = value` lines with JSON values on stderr and are
flushed before image checks, Git identity lookup, and sandbox creation. File
contents, environment variables, and forwarded agent arguments are not dumped.
The model and effort diagnostics report ExOShell's selected values (or `null`),
without inspecting native overrides or agent configuration.

## 4. Policies and providers

`policies/policy.yaml` is the portable baseline. Select it with the launcher's
`--policy` option or the configuration `policy` setting. Without a selected
policy, the launcher fails before image checks, Git identity lookup, or sandbox
creation. Selected policies must exist and be regular files; CLI paths resolve
relative to the caller and TOML paths relative to the selected configuration.
The explicit `--no-policy` option clears a configured policy and delegates
selection to OpenShell. OpenShell may select an environment or image policy;
its restrictive default applies only when no other policy source exists.
See ADR-0035.

Providers define credential bindings and endpoint rules independently of
filesystem grants. Import and create only the providers needed for a session;
providers.md documents the supported profiles. Avoid attaching profiles with
conflicting credential environment variables.

Supplied profile IDs start with `exoshell-` and carry the `exoshell-origin:
ExOShell` annotation. Suggested instance names drop a trailing `-cli`; registry
profiles and suggested instances use `-ro` for consumption without publishing.
The Codex fallback instance is `exoshell-codex`. Instance names remain configurable,
and origin metadata does not establish installer ownership. See ADR-0031.

GitHub and GitLab GraphQL endpoints are declared once per host in user policy,
allowing network overlays to replace an entry when enabling writes. Provider
profiles retain credential bindings and REST/Git transport rules. Overlay
composition replaces each named network policy entry in full and preserves
live static policy sections. Reversion restores network entries from the
selected baseline. PyYAML is required by `policy-overlays/apply.py`.

## 5. Optional integrations and lifecycle

Before starting Codex, the image helper runs `codex login --with-api-key`
when `OPENAI_API_KEY` is non-empty, supplying the current provider placeholder
through stdin. Each helper invocation refreshes the saved login; failure stops
startup without forwarding login output. Without a key, Codex retains its
normal login behavior. The image defaults to file-based credential storage
under `CODEX_HOME` (normally `/sandbox/.codex`); this state is discarded with
the sandbox. Bare Codex commands bypass initialization but can reuse the saved
login. See [ADR-0033](adrs/adr0033-provider-backed-codex-login.md).

A kubeconfig can be mounted read-only; its credentials remain readable inside
the sandbox. Google Workspace initialization instead writes provider-backed
placeholders to a private credentials file in tmpfs. The launcher always
mounts `/tmp/gws` as tmpfs. The image helper initializes GWS only when
`GWS_CLIENT_ID`, `GWS_CLIENT_SECRET`, and `GWS_REFRESH_TOKEN` are all non-empty;
it skips initialization when none are non-empty and fails before starting the
command when only some are present. GWS has no separate launcher opt-in.
Public package registries and Atlassian MCP access are opt-in provider integrations.

Atlassian MCP defaults to disabled. At agent startup, the image helper enables
the built-in entry only when the provider-backed `ATLASSIAN_MCP_BEARER_TOKEN`
environment value is non-empty. It overrides conflicting entry enablement for
Codex, Claude Code, and OpenCode while preserving unrelated configuration.
Claude user state is kept inside `/sandbox/.claude` through `CLAUDE_CONFIG_DIR`.
Provider changes require a fresh process environment and another helper
invocation; bare client commands bypass this startup decision.

Codex's CLI enablement override selects embedded mode for interactive sessions
and can produce a shared-background-server warning. This is accepted for the
disposable sandbox workflow; MCP remains supported. See
[ADR-0029](adrs/adr0029-codex-embedded-mode-for-provider-controlled-mcp.md).

OpenShell assigns sandbox names. The launcher adds `managed-by=exoshell`,
project, and agent labels and passes `--no-keep` by default. Agent state lives
in the container layer and is discarded at deletion; project files remain on
the host. With `--no-share`, the project label is `ephemeral` and workspace
files are discarded with the sandbox. `--keep` retains a sandbox for diagnosis
and requires later cleanup.

## 6. Customization and validation

Maintain organization-specific provider profiles, policies, image layers,
and model choices in a separate repository. Use an explicit upstream checkout
path and existing CLI/configuration interfaces; no organization-specific
launcher logic is required. See ADR-0027.

Run `python3 -m unittest discover -s tests -v` and the version-check skill tests.
Lint profiles and policies using the installed OpenShell CLI. On a capable
host, build the images and perform the identity, filesystem, inference, forge,
and lifecycle smoke checks described in README.md and CUSTOMIZATION.md.
