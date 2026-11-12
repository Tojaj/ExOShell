# Create a custom image

Start with [`sandboxes/exoshell-base`](https://github.com/Tojaj/ExOShell/tree/main/sandboxes/exoshell-base), which extends the
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
disabled `atlassian` entry (`enabled = false` or `"disabled": true` under
`mcp.servers`). The base image's `exoshell-agent` helper manages it from the
attached credential at startup (installing the canonical server definition
when the inline layer has none), including when OpenCode uses a custom
`OPENCODE_CONFIG` layer.
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
its global `instructions` list. See [ADR-0032](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0032-shared-image-agent-instructions.md).

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

OpenShell v0.1.5 supports private CA trust in the stock Podman supervisor.
Place an operator-owned PEM bundle at an absolute, gateway-readable path on the
**gateway host**, then add this setting to the existing
`[openshell.drivers.podman]` table in `~/.config/openshell/gateway.toml`:

```toml
additional_ca_bundle = "/etc/openshell/tls/additional-ca.pem"
```

The file must contain at least one valid certificate. OpenShell validates it
when the driver starts; unreadable or certificate-free bundles prevent gateway
startup. The setting works with direct egress and does not require `https_proxy`.
It augments the stock supervisor's public roots and the workload's injected
trust bundle. It applies to every Podman sandbox and destination on the gateway;
network policy still controls access.

Remove a `supervisor_image` override previously used only to add private roots.
The default supervisor image follows the installed OpenShell version. Restart
the gateway and create fresh sandboxes after changing the setting or CA bundle.
For remote gateways, install the PEM on the remote gateway host.

Derived workload images can still install their own roots for build-time
requests and clients that use the image's trust store. Keep private certificate
sources and host paths in the customization repository or machine-local setup.
See [ADR-0043](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0043-native-podman-additional-ca-bundle.md) and the
[upgrade guide](../upgrade-openshell-0.1.5.md). `proxy_ca_bundle` remains the
separate option for corporate forward proxies.

### Image requirements

- Run the workload as a non-root user. This project retains the community
  `sandbox` account and `/sandbox` home.
- Keep `/sandbox` and `/workspace` writable by the final process identity.
- Install tools at stable paths and list those resolved paths in policies and
  provider profiles. Wrapper paths alone may not be sufficient.
- Put only non-secret defaults in `/etc` or environment variables.
- Rebuild the custom and local-identity layers after changing the Dockerfile.
