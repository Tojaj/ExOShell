# Generic OpenShell sandbox image

This image extends the OpenShell community base with the command-line tools and
non-secret agent defaults used by this repository. It reuses the community
container identity:

| Setting | Value |
|---|---|
| User/group | `sandbox` |
| Home | `/sandbox` |
| Shared workspace mount | `/workspace` |
| OpenShell OCI workdir | `/sandbox` |
| Agent runtime state | Selected-agent tmpfs below `/sandbox` |

`/sandbox` remains the workdir because OpenShell manages that workspace. The
image includes `/usr/local/bin/exoshell-agent` to start a command in a selected
project below `/workspace`:

```text
exoshell-agent PROJECT -- COMMAND [ARG ...]
```

`PROJECT` must be an existing absolute directory whose resolved path stays
under `/workspace`. The helper changes into it and replaces itself with
`COMMAND`, passing arguments and exit status unchanged. OpenShell's sandbox
create command does not select the main process's workdir, so the launcher
passes the translated project path explicitly. Direct `openshell sandbox
create` users can pass the same invocation after `--`, with a writable host
share mounted at `/workspace`.

For example, from this repository, replace the image, host path, and provider
name with values configured on your gateway:

```bash
openshell sandbox create \
  --from localhost/exoshell-local:latest \
  --provider AGENT_PROVIDER \
  --policy ./policies/policy.yaml \
  --driver-config-json='{"podman":{"mounts":[{"type":"bind","source":"/absolute/path/to/share","target":"/workspace","read_only":false,"selinux_label":"shared"}]}}' \
  -- /usr/local/bin/exoshell-agent /workspace -- codex
```

To initialize GWS, attach a provider that
supplies non-empty `GWS_CLIENT_ID`, `GWS_CLIENT_SECRET`, and
`GWS_REFRESH_TOKEN`, and mount a tmpfs at `/tmp/gws`. The helper writes
`/tmp/gws/credentials.json` as a private `authorized_user` JSON file. It creates
`/tmp/gws/config` as a private directory for the GWS token and discovery caches,
then sets the GWS CLI path variables for the command. When none of the three
values are non-empty, it skips initialization; a partial set fails startup.
For a direct OpenShell GWS launch, add its provider and add
`{"type":"tmpfs","target":"/tmp/gws","mode":511}` to the same Podman
`mounts` array (`511` is the decimal value of mode `0777`).
The ExOShell launcher supplies this mount unconditionally, including for
providers attached after creation. After provider changes, wait for application
and invoke the helper through a fresh exec or SSH environment; an existing shell
keeps its original environment. Bare agent commands bypass initialization.
The tmpfs mount supplies the writable directory and keeps its credentials file
and GWS cache out of the container's writable layer. It is not required for
GWS itself: an image-created writable `/tmp/gws` would also work. With that
alternative, those files remain in a sandbox retained with `--keep` until it
is deleted; the normal `--no-keep` lifecycle deletes the container layer.

## Build

```bash
podman build -t exoshell-base sandboxes/exoshell-base
./sandboxes/local-user/build.sh
```

The second command is required for writable rootless-Podman bind mounts. It
creates a thin image that changes `sandbox` to the current host UID/GID. See
`../local-user/README.md` for base-image and tag overrides.

The image includes these command-line tools:

- `codex` — OpenAI coding agent.
- `claude` — Claude Code coding agent.
- `opencode` — OpenCode coding agent.
- `gws` — Google Workspace CLI for Docs, Drive, and other Workspace services.
- `glab` — GitLab CLI for repositories, merge requests, and CI.
- `oc`, `kubectl` — OpenShift and Kubernetes cluster CLIs.
- `uv`, `uvx` — Python package and tool runners.
- `rg` — fast text search across files.
- `fd` — fast file and directory search.
- `ast-grep` — structural code search and rewriting.
- `jq` — JSON querying and transformation.
- `pre-commit` — run repository commit hooks.
- `oras` — work with OCI registry artifacts.
- `skopeo` — inspect remote container images and copy them to local storage
  without a container daemon.
- `yq` — query and edit YAML files.
- `tkn` — inspect and run Tekton pipelines and tasks.

Package installation and downloads require an attached
[package registry provider](../../providers.md#opt-in-package-registries).
In particular, `uvx` cannot fetch Python MCP dependencies from PyPI without
the `exoshell-pypi-packages-ro` provider. Go and Cargo are not installed in this image.
Public image inspection and downloads with `skopeo` or `oras` require the
matching `exoshell-ghcr-registry-ro`, `exoshell-dockerhub-registry-ro`, or `exoshell-quay-registry-ro` provider.
Skopeo uses the distribution package version. Rebuild the base and derived
image layers to add it to existing installations.

Pinned tool version build arguments live in `Dockerfile`. Non-secret Codex
defaults are copied to `/etc/codex/config.toml`; OpenCode automatic updates are
disabled by global `/sandbox/.config/opencode/opencode.json` configuration.
Projects can override those OpenCode defaults with their own `opencode.json`.
TUI settings are in `/sandbox/.config/opencode/tui.json`; projects can override
them with their own `tui.json`.

`exoshell-agent` prepares Codex authentication before starting the requested
Codex command. With a non-empty `OPENAI_API_KEY`, it runs
`codex login --with-api-key` and supplies the attached provider's placeholder
through stdin, refreshing the login on each launch. Codex stores that value in
`CODEX_HOME/auth.json` (normally `/sandbox/.codex/auth.json`) with private
permissions; the real provider key remains outside the sandbox. Login failure
stops startup without printing captured output. Without the environment value,
Codex uses its normal login flow. Bare commands can reuse the prepared login
but do not initialize it themselves. Rebuild the base and all derived image
layers to enable this behavior. See [ADR-0033](../../adrs/adr0033-provider-backed-codex-login.md).

Small, sandbox-specific instructions for operational issues and image-provided
tools live in `agent-instructions/`. The image installs them as root-owned,
readable files under `/etc/exoshell/instructions/`. At build time,
`render-agent-instructions.py` combines the Markdown files in filename order
and adds the content to Codex's top-level `developer_instructions` in
`/etc/codex/config.toml` and Claude's managed `/etc/claude-code/CLAUDE.md`.
OpenCode lists the individual installed files explicitly in its global
configuration. Add new files to that list as well as the source directory.

These instructions load for direct agent launches as well as launches through
`exoshell-agent`, independently of `CODEX_HOME` and `CLAUDE_CONFIG_DIR`.
Codex treats them as developer instructions; higher-precedence configuration
can replace the entire value. Claude's managed memory supplies behavioral
guidance, not technical enforcement. Rebuild the base and derived images after
changing the sources. See [ADR-0032](../../adrs/adr0032-shared-image-agent-instructions.md)
and [derived-image instructions](../../CUSTOMIZATION.md#shared-agent-instructions).

Atlassian MCP is disabled by default. `exoshell-agent` enables it at startup
only with a non-empty provider credential placeholder. Runtime overrides
control the `atlassian` entry even when a project config disagrees. Claude's
non-secret MCP template is installed at `/etc/exoshell/claude-atlassian.json`;
the helper registers it in `/sandbox/.claude/.claude.json` only when enabled.
`CLAUDE_CONFIG_DIR=/sandbox/.claude` keeps mutable Claude state within the
existing writable policy. See [Atlassian setup and smoke checks](../../providers.md#atlassian-rovo-mcp).

## Agent skills

The inherited `github` skill remains available. This image adds the official
version-matched `glab` skill and ExOShell companions for GitLab and GitHub.
The companions explain host selection, provider-backed credentials, and policy
behavior; they do not contain credentials or host-specific configuration.
Skills are available through `/sandbox/.agents/skills` and symlinked into
`/sandbox/.claude/skills` for Claude Code discovery.

No credentials, kubeconfig, host home, or agent user configuration are copied
into the image. The launcher attaches optional host files; the image helper
initializes GWS placeholders when all three provider credentials are available.
It also recomputes Atlassian MCP state from the attached credential at each
supported agent startup.

## Smoke checks

After launching a sandbox:

```bash
id -un
printf '%s\n' "$HOME" "$PWD"
command -v codex claude opencode gws glab oc kubectl uv uvx rg fd ast-grep jq pre-commit oras yq tkn
touch /workspace/.openshell-write-test
rm /workspace/.openshell-write-test
```

The expected user is `sandbox`, home is `/sandbox`, and the write-test file is
owned by the host user.
