# Opt-in package registries

*Run these commands on the gateway host, from your ExOShell checkout: the paths
are relative to it. Blocks marked as sandbox commands run inside a sandbox.*

Eight independent, credential-free profiles grant package or container image
downloads and metadata lookups. None is attached by default or grants publishing
access. Follow the profile links for their exact endpoint and executable rules.

| Profile / instance (YAML) | Use it for |
| --- | --- |
| [`exoshell-npm-registry-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-npm-registry.yaml) | npm packages, search, audit requests, and Node runtime downloads |
| [`exoshell-pypi-packages-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-pypi-packages.yaml) | Python packages and metadata through pip, uv, or uvx |
| [`exoshell-go-modules-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-go-modules.yaml) | Go runtime downloads, module proxy access, and checksum verification |
| [`exoshell-cargo-crates-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-cargo-crates.yaml) | Cargo crates, index, search, and metadata |
| [`exoshell-ubuntu-apt-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-ubuntu-apt.yaml) | Ubuntu package indexes and downloads over HTTP/HTTPS |
| [`exoshell-ghcr-registry-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-ghcr-registry.yaml) | Public images and artifacts from GitHub Container Registry |
| [`exoshell-dockerhub-registry-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-dockerhub-registry.yaml) | Public images and artifacts from Docker Hub |
| [`exoshell-quay-registry-ro`](https://github.com/Tojaj/ExOShell/blob/main/provider-profiles/provider-quay-registry.yaml) | Public images and artifacts from Quay.io |

## Set up an ecosystem

Choose a tab and run its commands for each ecosystem your project needs. These
profiles require no credentials; omit credential and discovery flags.

=== "npm"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-npm-registry.yaml
    openshell provider profile import -f provider-profiles/provider-npm-registry.yaml
    openshell provider create --name exoshell-npm-registry-ro \
      --type exoshell-npm-registry-ro
    ```

=== "PyPI"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-pypi-packages.yaml
    openshell provider profile import -f provider-profiles/provider-pypi-packages.yaml
    openshell provider create --name exoshell-pypi-packages-ro \
      --type exoshell-pypi-packages-ro
    ```

=== "Go"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-go-modules.yaml
    openshell provider profile import -f provider-profiles/provider-go-modules.yaml
    openshell provider create --name exoshell-go-modules-ro \
      --type exoshell-go-modules-ro
    ```

=== "Cargo"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-cargo-crates.yaml
    openshell provider profile import -f provider-profiles/provider-cargo-crates.yaml
    openshell provider create --name exoshell-cargo-crates-ro \
      --type exoshell-cargo-crates-ro
    ```

=== "Ubuntu APT"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-ubuntu-apt.yaml
    openshell provider profile import -f provider-profiles/provider-ubuntu-apt.yaml
    openshell provider create --name exoshell-ubuntu-apt-ro \
      --type exoshell-ubuntu-apt-ro
    ```

=== "GHCR"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-ghcr-registry.yaml
    openshell provider profile import -f provider-profiles/provider-ghcr-registry.yaml
    openshell provider create --name exoshell-ghcr-registry-ro \
      --type exoshell-ghcr-registry-ro
    ```

=== "Docker Hub"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-dockerhub-registry.yaml
    openshell provider profile import -f provider-profiles/provider-dockerhub-registry.yaml
    openshell provider create --name exoshell-dockerhub-registry-ro \
      --type exoshell-dockerhub-registry-ro
    ```

=== "Quay"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-quay-registry.yaml
    openshell provider profile import -f provider-profiles/provider-quay-registry.yaml
    openshell provider create --name exoshell-quay-registry-ro \
      --type exoshell-quay-registry-ro
    ```

For an already-imported profile, follow [Update provider profiles](update-provider-profiles.md).

## Attach instances to a session

For repeat use, add the selected instance names to the common `providers`
array in [`.exoshell.local.toml`](../guide/configuration.md) so Codex, Claude Code,
and OpenCode all get them. For one run, repeat `--provider` for **every** desired
instance, including the inference provider: CLI options replace the complete
configured list. For example, after creating the Codex and npm instances:

```bash
./run-exoshell-agent.sh --policy policies/policy.yaml --agent codex \
  --provider exoshell-codex --provider exoshell-npm-registry-ro .
```

Providers grant network access; they do not install tools. The base image
includes npm and uv/uvx, but Go and Cargo need separate installation, such as
in a [derived image](../customize/images.md). Check the profile's executable
rules when using a custom installation. Python package downloads, including
Python MCP server dependencies installed through uvx, need the PyPI provider.

!!! note "pre-commit hooks"
    Hooks may need ecosystem providers beyond those used by your project:
    for example, PyPI for Python hooks, npm for Node hooks, or Go for Go hooks.
    The npm and Go profiles also permit runtime downloads for hook setup.
    See [ADR-0039](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0039-ecosystem-runtime-downloads.md)
    for runtime and custom-cache details.

## Ubuntu APT

The APT profile covers Ubuntu's main, security, ports, and old-release archives
over HTTP and HTTPS. Country mirrors, PPAs, Ubuntu Pro/ESM, and third-party
repositories need custom profiles and APT source configuration; attaching a
provider does not change those sources.

With the APT instance attached, verify archive access inside the sandbox:

```bash
# inside the sandbox
curl --fail --silent --show-error --output /tmp/ubuntu-InRelease \
  http://archive.ubuntu.com/ubuntu/dists/noble/InRelease
```

System package installation also needs appropriate privileges and writable
APT/dpkg state and installation paths. The baseline policy keeps system paths
read-only. Add packages to a [derived image](../customize/images.md), or use a
separately configured sandbox policy when installation inside a sandbox is needed.

## Container registries

The GHCR, Docker Hub, and Quay profiles allow public image metadata, manifests,
and layer downloads through `skopeo`, `oras`, `curl`, Python tools, and agents.
They require no login and do not configure private-image authentication.
These grants apply to requests inside the sandbox; host and gateway image pulls
use their own network access. Docker Hub's anonymous pull limits still apply.

With the Docker Hub instance attached, use Skopeo to inspect a public image or
copy its layers to a writable local OCI layout:

```bash
# inside the sandbox
skopeo inspect docker://docker.io/library/alpine:latest
skopeo copy docker://docker.io/library/alpine:latest oci:/tmp/alpine-smoke:latest
```

## Private mirrors and enterprise registries

Adapt a profile in a [separate customization repository](../customize/index.md#separate-customization-repository).
Give it a new filename, profile ID, display name, and origin metadata; replace
its endpoints with the required registry, download, and checksum hosts, and
bind credentials explicitly when authentication is needed. Lint and import
the profile, then create an instance.

Configure the package client to use the mirror separately; attaching a provider
does not reconfigure clients. When restricting public access, review the entire
effective sandbox policy, all attached providers, and client fallback settings:
a private profile does not remove grants supplied by other layers.
