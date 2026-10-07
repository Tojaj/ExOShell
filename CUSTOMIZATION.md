# Customizing this project

This repository is intended to be adapted to local tools, policies, and source
control services. Keep machine-specific values in `.exoshell.local.toml`, keep
credentials in OpenShell providers, and put only non-secret configuration in
images and committed YAML files.

The launcher loads one configuration file: explicit `--config PATH`, then
`.exoshell.local.toml` in the caller's current directory, then
`$XDG_CONFIG_HOME/exoshell/exoshell.local.toml`, then
`/etc/exoshell/exoshell.local.toml`. The user directory defaults to
`~/.config` when `XDG_CONFIG_HOME` is unset, empty, or relative. Explicit
config accepts any filename, resolves relative to the caller's directory,
and bypasses discovery. Absent discovery candidates are skipped; invalid,
unreadable, or non-file candidates and missing explicit files are errors.
Only the selected file is loaded. Missing keys use built-in defaults without
inheriting lower-priority settings, and CLI options override file settings.
TOML paths resolve relative to the selected file; CLI paths use the caller's
directory.

Discovery uses the caller's directory, independently of the positional
project and launcher locations. It does not search parents, uppercase aliases,
or `XDG_CONFIG_DIRS`. Existing checkout configs remain discoverable when
running from that checkout. When calling the launcher elsewhere, supply
`--config` or move the config into the user directory, adjusting relative
paths as needed. See [ADR-0034](adrs/adr0034-launcher-config-discovery.md).

The main extension points are:

| Need | Extension point |
|---|---|
| Additional CLIs, workload CA certificates, or managed agent defaults | Derived sandbox image |
| Private CA for inspected Podman HTTPS egress | Derived supervisor image and gateway `supervisor_image` |
| Filesystem and network access | Sandbox policy |
| Credential injection and provider-owned endpoint access | Provider profile and provider instance |
| Machine paths, selected image, policy, and provider names | `.exoshell.local.toml` |

Use reserved example domains such as `github.example.com` and
`gitlab.example.com` while preparing changes for publication. Never commit
tokens, authenticated CLI configuration, private keys, kubeconfigs, or files
copied from a host home directory.

## Separate customization repository

Keep site-specific profiles, policies, image layers, and model selections in a
separate repository when their contents should not be published. Consume an
explicit upstream checkout path instead of copying or modifying the launcher.
Record the upstream version tested by the customization repository.

For example, with public sources in `../ExOShell` and configuration in the
current customization repository:

```bash
../ExOShell/run-exoshell-agent.sh --config "$PWD/.exoshell.local.toml" /path/to/project
../ExOShell/policy-overlays/apply.py --sandbox <sandbox-name> \
  --base-file "$PWD/policies/policy-local.yaml" --revert \
  "$PWD/policy-overlays/example-issues.yaml"
```

TOML file paths resolve relative to that file, so `policy =
"policies/policy-local.yaml"` can stay within the customization repository.
The overlay helper's automatic baseline lookup still uses its own checkout's
local configuration. Overlay users must supply the correct `--base-file`
explicitly; launcher discovery does not determine the helper's baseline.
Build the generic image from the selected checkout, then the custom workload
and optional supervisor, and finally use the upstream local-user build script
with `--base-image` and `--tag` to select the custom ownership layer.

See [ADR-0027](adrs/adr0027-separate-customization-repository.md).

## Create a custom image

Start with [`sandboxes/exoshell-base`](sandboxes/exoshell-base/), which extends the
OpenShell community image with the agents and CLIs expected by this project.
Create another layer when you need organization-specific trust roots, extra
tools, or non-secret client configuration.

For example:

```text
sandboxes/example-base/
|-- Dockerfile
|-- organization-ca.crt
`-- glab-config.yml
```

```dockerfile
# syntax=docker/dockerfile:1
ARG BASE_IMAGE=localhost/exoshell-base:latest
FROM ${BASE_IMAGE}

USER root

# Optional: install a CA needed to verify services using a private PKI.
# The file must contain certificates only, never a client key.
COPY --chmod=0644 organization-ca.crt \
    /usr/local/share/ca-certificates/organization-ca.crt
RUN update-ca-certificates

# Optional: register a GitLab host without storing a token.
COPY --chown=sandbox:sandbox glab-config.yml /etc/glab-cli/config.yml
RUN chmod 0600 /etc/glab-cli/config.yml

# The launcher selects configured GitHub and GitLab hosts at sandbox creation.
ENV GLAB_CONFIG_DIR=/etc/glab-cli \
    GLAB_CHECK_UPDATE=false

WORKDIR /sandbox
USER sandbox
ENTRYPOINT ["/bin/bash"]
```

When replacing Codex or OpenCode defaults in a derived image, retain the
disabled `atlassian` entry (`enabled = false` or `"enabled": false`). The base
image's `exoshell-agent` helper enables it from the attached credential at
startup, including when OpenCode uses a custom `OPENCODE_CONFIG` layer.
Keep Claude's inherited `CLAUDE_CONFIG_DIR` within a writable agent-state
directory; its default is `/sandbox/.claude`.

The token-free GitLab configuration contains host metadata only:

```yaml
hosts:
  gitlab.example.com:
    git_protocol: https
    api_protocol: https
```

Do not copy `~/.config/glab-cli`, `~/.config/gh`, or similar host configuration
into the image. Those files commonly contain plaintext credentials. Provider
environment placeholders should remain the only credential source.

Build the layers in order:

```bash
podman build -t exoshell-base sandboxes/exoshell-base
podman build -t example-base sandboxes/example-base
./sandboxes/local-user/build.sh \
  --base-image localhost/example-base:latest \
  --tag example-local
```

The final local layer remaps the image's `sandbox` account to the current host
UID and GID. This is required for writable rootless-Podman bind mounts and keeps
personal numeric IDs out of shared Dockerfiles.

Select the resulting image in the ignored local configuration:

```toml
image = "localhost/example-local:latest"
```

For a remote gateway, push the image to a registry the gateway can access and
use that fully qualified image reference. OpenShell does not build a Dockerfile
passed to `--from`; build and tag the image first.

### Shared agent instructions

The base image keeps operational guidance under `/etc/exoshell/instructions/`.
At build time, it combines all top-level `*.md` files in filename order into
Codex's `developer_instructions` in `/etc/codex/config.toml` and Claude's
`/etc/claude-code/CLAUDE.md`. OpenCode references the individual files through
its global `instructions` list. See [ADR-0032](adrs/adr0032-shared-image-agent-instructions.md).

To add organization-specific guidance in a derived image, install additional
Markdown files, copy a fresh Codex configuration template without
`developer_instructions`, and rerun the installed build helper as root:

```dockerfile
USER root
COPY --chmod=0644 agent-instructions/ /etc/exoshell/instructions/
COPY --chmod=0644 codex.config.toml /etc/codex/config.toml
RUN python3 /usr/local/lib/exoshell/render-agent-instructions.py
USER sandbox
```

Start the fresh Codex template from the base image's source
`sandboxes/exoshell-base/codex.config.toml`, preserving its existing defaults
and disabled Atlassian MCP entry. The helper rejects a template that already
contains `developer_instructions`; copying the generated configuration from
a running image is unsuitable. It writes the complete combined content to
both agents' system files. Rebuild every dependent image after changes.

For OpenCode, also update the global `instructions` list to include every
installed Markdown file, retaining the base files and unrelated settings.
Editing Markdown alone does not refresh Codex or Claude's generated content.
Higher-precedence Codex configuration can replace `developer_instructions`
as a whole; it does not append to the image's value. These instructions have
developer-level priority over project guidance. Claude's managed memory
cannot be excluded through `claudeMdExcludes`, but remains behavioral guidance
rather than technical enforcement.

### Private CA for inspected Podman HTTPS egress

On OpenShell 0.1.2, Podman runs the network supervisor in a separate container.
The `organization-ca.crt` installed in `example-base` lets workload clients
verify private-CA services, but it does not let the supervisor verify inspected
upstream HTTPS connections. Build a matching supervisor image with the same CA
bundle:

```text
sandboxes/example-supervisor/
`-- Dockerfile
```

```dockerfile
# syntax=docker/dockerfile:1
ARG CA_IMAGE=localhost/example-base:latest
ARG SUPERVISOR_IMAGE=ghcr.io/nvidia/openshell/supervisor:0.1.2

FROM ${CA_IMAGE} AS ca-source
FROM ${SUPERVISOR_IMAGE}

COPY --from=ca-source /etc/ssl/certs/ca-certificates.crt \
    /etc/ssl/certs/ca-certificates.crt
```

Set `SUPERVISOR_IMAGE` to the official supervisor image matching your installed
OpenShell release, either in the Dockerfile or with `--build-arg`. The copied
bundle replaces the supervisor image's system bundle, so keep the public roots
your deployment needs in `example-base`.
Build this image after `example-base`:

```bash
podman build -t example-supervisor sandboxes/example-supervisor
```

In the gateway host's `~/.config/openshell/gateway.toml`, add this setting to
the existing `[openshell.drivers.podman]` table:

```toml
supervisor_image = "localhost/example-supervisor:latest"
```

Restart the gateway and create a fresh sandbox. For a remote gateway, push the
supervisor image to a registry it can access and use its fully qualified image
reference. This gateway setting gives every Podman sandbox's supervisor the
extra trust anchors; each sandbox's network policy still controls its allowed
destinations. Rebuild the supervisor image when OpenShell is upgraded or the
private CA changes.

In OpenShell 0.1.2, Podman's `proxy_ca_bundle` requires `https_proxy`, so it does
not serve direct egress. See
[ADR-0026](adrs/adr0026-custom-podman-supervisor-ca-bundle.md) and
[upstream issue #3781](https://github.com/NVIDIA/OpenShell/issues/3781) for the
reason this separate image is needed and the upstream fix request.

### Image requirements

- Run the workload as a non-root user. This project retains the community
  `sandbox` account and `/sandbox` home.
- Keep `/sandbox` and `/workspace` writable by the final process identity.
- Install tools at stable paths and list those resolved paths in policies and
  provider profiles. Wrapper paths alone may not be sufficient.
- Put only non-secret defaults in `/etc` or environment variables.
- Rebuild the custom and local-identity layers after changing the Dockerfile.

## Create a custom policy

Copy [`policies/policy.yaml`](policies/policy.yaml) and make the smallest
changes needed for the local environment:

```bash
cp policies/policy.yaml policies/policy-local.yaml
```

Then select it in `.exoshell.local.toml`:

```toml
policy = "policies/policy-local.yaml"
```

Decide whether the derived policy is safe to commit. Hostnames can reveal
internal infrastructure even when the file contains no credentials. Keep a
site-specific policy outside a public branch when its endpoint inventory is
sensitive.

### Policy sections

- `filesystem_policy` lists readable and writable container paths. Paths not
  admitted by the effective Landlock policy are inaccessible.
- `landlock` controls whether missing paths degrade gracefully or fail sandbox
  startup.
- `process` should remain `sandbox` when using this project's images.
- `network_policies` pair destination endpoints with the exact binaries allowed
  to reach them.

Filesystem, Landlock, and process settings become static after sandbox startup.
Network policy can be hot-reloaded.

This example adds read-only API access for a tool installed in the custom
image:

```yaml
network_policies:
  example_service:
    name: example-service
    endpoints:
      - host: api.example.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-only
    binaries:
      - { path: /usr/local/bin/example-cli }
```

Prefer `enforcement: enforce` for known behavior. `audit` is useful while
discovering required endpoints, but it permits traffic and should not become a
permanent substitute for scoped rules.

Important composition rules:

- Attached provider profiles add `_provider_*` entries to the effective
  policy. Do not duplicate those broad host entries in the user policy.
- Equal-specificity entries for the same host and port must agree on protocol
  and enforcement. In particular, an `audit` endpoint can conflict with an
  attached provider's `enforce` endpoint.
- `access` and `rules` are mutually exclusive on one endpoint.
- A policy allow does not widen a provider credential's endpoint binding. A
  custom host must also appear in the provider profile that owns its token.
- Binary paths are security boundaries. Confirm the executable's actual path
  inside the image with `command -v` and, for wrappers, inspect the resolved
  executable as well.

### GraphQL endpoints

The source-control profiles in this repository deliberately omit GraphQL
endpoints. Declare each GraphQL endpoint exactly once in the user policy so a
policy overlay can replace the baseline rule instead of intersecting with a
provider-owned rule.

For self-hosted GitHub and GitLab instances:

```yaml
network_policies:
  github_enterprise_graphql:
    name: github-enterprise-graphql
    endpoints:
      - host: github.example.com
        port: 443
        path: /api/graphql
        protocol: graphql
        access: read-only
        enforcement: enforce
    binaries:
      - { path: /usr/bin/gh }
      - { path: /usr/local/bin/gh }

  gitlab_enterprise_graphql:
    name: gitlab-enterprise-graphql
    endpoints:
      - host: gitlab.example.com
        port: 443
        path: /api/graphql
        protocol: graphql
        access: read-only
        enforcement: enforce
    binaries:
      - { path: /usr/bin/glab }
      - { path: /usr/local/bin/glab }
```

`read-only` permits GraphQL queries, not mutations. Add narrowly scoped policy
overlays for required mutations; do not add a second matching GraphQL endpoint.
See [`policy-overlays/README.md`](policy-overlays/README.md) for this project's
overlay workflow.

### Iterate and verify

Create a sandbox with the policy, inspect denied requests, and update only the
required rules:

```bash
./run-exoshell-agent.sh --policy policies/policy-local.yaml .
openshell logs codex --tail --source sandbox
openshell policy get codex --full
```

For a running sandbox, network-only changes can be applied without recreation:

```bash
openshell policy get codex --base > /tmp/current-policy.yaml
# Remove the metadata header above the YAML document marker before reuse.
openshell policy set codex --policy /tmp/current-policy.yaml --wait
```

Recreate the sandbox after changing static policy sections or after adding the
first `protocol: tcp` endpoint.

## Create custom source-control providers

A provider profile defines a reusable provider type: credential environment
variables, endpoint bindings, allowed request shapes, and permitted binaries.
A provider instance stores the actual local credential for that type.

Provider profile hosts are not parameterized when an instance is created. Make
one profile YAML and one unique profile ID for each source-control host.

### GitHub Enterprise profile

Create `provider-profiles/provider-github-enterprise-cli.yaml` and replace the
example hostname with the real GitHub Enterprise Server hostname:

```yaml
id: github-enterprise-cli
display_name: GitHub Enterprise (CLI)
description: GitHub Enterprise API and read-only Git HTTPS access
category: source_control
credentials:
  - name: api_token
    description: GitHub Enterprise access token
    env_vars: [GH_ENTERPRISE_TOKEN, GITHUB_ENTERPRISE_TOKEN]
    required: true
    auth_style: bearer
    header_name: authorization
discovery:
  credentials: [api_token]
endpoints:
  - host: github.example.com
    port: 443
    protocol: rest
    enforcement: enforce
    rules:
      - allow: { method: GET, path: "/api/v3/**" }
      - allow: { method: HEAD, path: "/api/v3/**" }
      - allow: { method: OPTIONS, path: "/api/v3/**" }
      - allow: { method: GET, path: "/**/info/refs*" }
      - allow: { method: POST, path: "/**/git-upload-pack" }
binaries:
  - /usr/bin/gh
  - /usr/local/bin/gh
  - /usr/bin/git
  - /usr/local/bin/git
  - /usr/lib/git-core/**
  - /usr/bin/codex
  - /usr/local/bin/codex
  - /usr/lib/node_modules/@openai/**
  - /usr/local/bin/claude
  - /usr/bin/claude
  - /usr/local/bin/opencode
  - /usr/bin/opencode
  - /usr/lib/node_modules/opencode-ai/**
  - /usr/bin/curl
```

The GitHub Enterprise REST API normally uses `/api/v3` and GraphQL uses
`/api/graphql`. Confirm those paths for the deployed version. Keep the GraphQL
endpoint in the user policy as described above.

The profile exports the enterprise-specific variables expected by `gh`. Set the
same host in `.exoshell.local.toml`:

```toml
github_host = "github.example.com"
```

The launcher sets `GH_HOST`, rewrites matching SSH-style Git remotes to HTTPS,
and configures Git to use `gh auth git-credential`. This selects the CLI and Git
host only; it does not replace the host-specific provider profile or GraphQL
policy entry.

### GitLab self-managed profile

Create `provider-profiles/provider-gitlab-enterprise-cli.yaml`:

```yaml
id: gitlab-enterprise-cli
display_name: GitLab Self-Managed (CLI)
description: GitLab API and read-only Git HTTPS access
category: source_control
credentials:
  - name: api_token
    description: GitLab access token
    env_vars: [GITLAB_TOKEN, GLAB_TOKEN]
    required: true
    auth_style: bearer
    header_name: authorization
discovery:
  credentials: [api_token]
endpoints:
  - host: gitlab.example.com
    port: 443
    protocol: rest
    enforcement: enforce
    allow_encoded_slash: true
    rules:
      - allow: { method: GET, path: "**" }
      - allow: { method: HEAD, path: "**" }
      - allow: { method: OPTIONS, path: "**" }
      - allow: { method: POST, path: "/**/git-upload-pack" }
binaries:
  - /usr/bin/glab
  - /usr/local/bin/glab
  - /usr/bin/git
  - /usr/local/bin/git
  - /usr/lib/git-core/**
  - /usr/bin/codex
  - /usr/local/bin/codex
  - /usr/lib/node_modules/@openai/**
  - /usr/local/bin/claude
  - /usr/bin/claude
  - /usr/local/bin/opencode
  - /usr/bin/opencode
  - /usr/lib/node_modules/opencode-ai/**
  - /usr/bin/curl
```

`allow_encoded_slash` is needed for common GitLab API paths. GitLab REST and
Git HTTPS share one host, so explicit request rules are used instead of an
`access` preset. Keep `/api/graphql` in the user policy.

Set the launcher host in `.exoshell.local.toml`:

```toml
gitlab_host = "gitlab.example.com"
```

The launcher then sets `GITLAB_HOST`, rewrites matching SSH-style Git remotes to
HTTPS, and configures a Git credential helper that sends the provider-backed
placeholder. The token-free `glab-config.yml` in the image registers the host
without persisting its token.

### Lint and import profiles

Lint each profile before importing it:

```bash
openshell provider profile lint \
  -f provider-profiles/provider-github-enterprise-cli.yaml
openshell provider profile lint \
  -f provider-profiles/provider-gitlab-enterprise-cli.yaml

openshell provider profile import \
  -f provider-profiles/provider-github-enterprise-cli.yaml
openshell provider profile import \
  -f provider-profiles/provider-gitlab-enterprise-cli.yaml
```

Profile import is create-only. To update an imported profile, export it first,
preserve its `resource_version`, apply the edits to that exported document, and
submit an update:

```bash
openshell provider profile export github-enterprise-cli -o yaml \
  > /tmp/github-enterprise-cli.yaml
openshell provider profile update github-enterprise-cli \
  -f /tmp/github-enterprise-cli.yaml
```

Updating a profile changes every provider instance of that type and reaches
running sandboxes on their next configuration sync. OpenShell rejects an update
that would make an attached sandbox's effective policy invalid.

### Create provider instances

Load each token into the host environment only long enough to create its
provider:

```bash
read -rsp "GitHub Enterprise token: " GH_ENTERPRISE_TOKEN
printf '\n'
export GH_ENTERPRISE_TOKEN
openshell provider create \
  --name github-enterprise \
  --type github-enterprise-cli \
  --from-existing
unset GH_ENTERPRISE_TOKEN

read -rsp "GitLab token: " GITLAB_TOKEN
printf '\n'
export GITLAB_TOKEN
openshell provider create \
  --name gitlab-enterprise \
  --type gitlab-enterprise-cli \
  --from-existing
unset GITLAB_TOKEN
```

Do not put token values directly in documentation, TOML, policy YAML, image
layers, or shell scripts. `--from-existing` uses the profile's `discovery`
section and stores the credential through the gateway's credential storage.

Attach the named instances through `.exoshell.local.toml`:

```toml
image = "localhost/example-local:latest"
policy = "policies/policy-local.yaml"
providers = ["github-enterprise", "gitlab-enterprise"]
github_host = "github.example.com"
gitlab_host = "gitlab.example.com"
```

Provider names are local choices; profile IDs must match the imported profile.
Use your own namespace and origin metadata for definitions you maintain; the
`exoshell-` prefix and `exoshell-origin: ExOShell` identify supplied definitions.
Do not attach two GitHub profiles that export the same environment variable, or
two GitLab profiles that export `GITLAB_TOKEN` and `GLAB_TOKEN`, to one sandbox.
Use separate sandboxes when switching between same-service instances.

## Smoke tests

After recreating the sandbox, verify identity and configuration without printing
credential variables:

```bash
id -un
printf '%s\n' "$HOME" "$PWD"
command -v gh glab git
printf '%s\n' "$GH_HOST" "$GITLAB_HOST"
gh auth status --hostname github.example.com
glab auth status --hostname gitlab.example.com
git ls-remote https://github.example.com/example/project.git
git ls-remote https://gitlab.example.com/example/project.git
```

Expected results:

- The user is `sandbox`, home is `/sandbox`, and the project is below
  `/workspace`.
- API queries, clone, and fetch work at baseline.
- API mutations and Git pushes remain blocked until explicitly allowed by both
  policy and token scope.
- `openshell policy get <sandbox> --full` contains one GraphQL endpoint for
  each configured source-control host.

When a request fails, inspect `openshell logs <sandbox> --tail --source sandbox`.
Check the destination, binary path, HTTP method and path, policy enforcement,
and `credential_endpoint_mismatch`. Fix a credential endpoint mismatch in the
provider profile only when the destination is an intended credential recipient;
widening user policy alone does not change credential binding.

## Upstream references

- [OpenShell provider profiles](https://docs.nvidia.com/openshell/sandboxes/providers-v2)
- [OpenShell policy schema](https://docs.nvidia.com/openshell/reference/policy-schema)
- [OpenShell compute drivers and custom
  images](https://docs.nvidia.com/openshell/reference/sandbox-compute-drivers)
- [`sandboxes/exoshell-base/README.md`](sandboxes/exoshell-base/README.md)
- [`sandboxes/local-user/README.md`](sandboxes/local-user/README.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
