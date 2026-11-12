# Get started

This guide takes you from a Linux host to your first disposable agent session.
Run these commands **on the gateway host** — the machine running the OpenShell
gateway, which on a single-machine setup is the Linux box in front of you — and
from your ExOShell checkout unless stated otherwise. The gateway creates and
supervises *sandboxes*: the disposable containers your agent runs in.

## 1. Prepare the host

You need:

- Rootless Podman, Git, and Python **3.11 or newer**.
- NVIDIA OpenShell **0.1.5 or newer**, with an authenticated, running gateway.
- An API key for the inference provider you choose below.

Install OpenShell using its [upstream documentation](https://docs.nvidia.com/openshell/).
If upgrading an existing installation, follow the [migration guide](upgrade-openshell-0.1.5.md).

```bash
git clone https://github.com/Tojaj/ExOShell.git
cd ExOShell
openshell --version
openshell status
```

## 2. Configure the gateway

Merge these settings into `~/.config/openshell/gateway.toml` on the gateway host.
Preserve unrelated settings and restart the gateway through your installation's
normal service management after changing them.

```toml
[openshell]
version = 2

[openshell.gateway]
compute_driver = "podman"

[openshell.drivers.podman]
allow_driver_config = true
enable_bind_mounts = true
userns = "keep-id"

[openshell.drivers.podman.resource_admission]
enabled = false
```

!!! warning "Use a trusted local gateway"
    These settings permit caller-selected host bind mounts and disable Podman
    resource admission. Use this setup only where gateway users are trusted to
    choose host paths. See [ADR-0025](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0025-podman-bind-mount-admission.md).

If sandboxes must reach services behind a private certificate authority, add
`additional_ca_bundle` to the same `[openshell.drivers.podman]` table now; see
[private CA trust](customize/images.md#private-ca-for-inspected-podman-https-egress).

## 3. Build the images

```bash
./build.sh
```

This builds the shared tools image and a local layer that maps the `sandbox`
account to your host UID/GID. Both this local layer and `userns = "keep-id"`
are needed for writable project mounts.

## 4. Set up one inference provider

A *provider profile* defines a reusable provider type: which credential it
carries and which endpoints and binaries may use it. A *provider instance* is
one local copy of that type holding your actual key, which OpenShell resolves
into permitted requests so the agent only ever sees a placeholder. See
[providers](integrations/index.md) for the full rules.

Choose one tab. Import the profile once, then create its credential-bearing
instance. The credential command prompts for the API key; keep keys out of
configuration files and command-line literals.

=== "Codex"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-codex-cli.yaml
    openshell provider profile import -f provider-profiles/provider-codex-cli.yaml
    openshell provider create --name exoshell-codex \
      --type exoshell-codex-cli --credential OPENAI_API_KEY
    ```

    ```bash
    ./run-exoshell-agent.sh --agent codex \
      --policy policies/policy.yaml --provider exoshell-codex /path/to/project
    ```

=== "Claude Code"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-claude-code-cli.yaml
    openshell provider profile import -f provider-profiles/provider-claude-code-cli.yaml
    openshell provider create --name exoshell-claude-code \
      --type exoshell-claude-code-cli --credential ANTHROPIC_API_KEY
    ```

    ```bash
    ./run-exoshell-agent.sh --agent claude \
      --policy policies/policy.yaml --provider exoshell-claude-code /path/to/project
    ```

=== "OpenCode (OpenRouter)"

    ```bash
    openshell provider profile lint -f provider-profiles/provider-opencode-openrouter.yaml
    openshell provider profile import -f provider-profiles/provider-opencode-openrouter.yaml
    openshell provider create --name exoshell-opencode-openrouter \
      --type exoshell-opencode-openrouter --credential OPENROUTER_API_KEY
    ```

    ```bash
    ./run-exoshell-agent.sh --agent opencode \
      --policy policies/policy.yaml --provider exoshell-opencode-openrouter /path/to/project
    ```

    Select an OpenRouter model in the agent. Do not use `/connect`, which writes
    readable credentials; the attached provider supplies the key placeholder.

Replace `/path/to/project` with an existing host directory. `policies/policy.yaml`
is this project's portable baseline *policy*: the file that decides which paths
and network destinations the sandbox may use. A policy is mandatory, so the
launcher stops when none is selected; see [custom policies](customize/policies.md)
to adapt it.

Ask the agent to report its user and working directory: expect `sandbox` and
`/workspace` when only the project is shared. Exit the agent to delete the
sandbox; project edits remain on the host.

Already imported a profile? Use the [update procedure](integrations/index.md#provider-lifecycle)
instead of importing it again. See [inference providers](integrations/inference.md)
for other backends and authentication details.

## 5. Make subsequent launches shorter

Create an ignored `.exoshell.local.toml` in the ExOShell checkout with only the
settings you need. For the Codex example:

```toml
policy = "policies/policy.yaml"
agent = "codex"
providers = ["exoshell-codex"]
```

From that checkout, launch with:

```bash
./run-exoshell-agent.sh /path/to/project
```

Configuration discovery starts in the caller's current directory. To call the
launcher from elsewhere, pass `--config /path/to/ExOShell/.exoshell.local.toml`
or set up a [user configuration](guide/configuration.md).

Add [package registry providers](integrations/registries.md) when your project
needs dependency downloads, and [forge providers](integrations/forges.md) for
GitHub or GitLab access. Neither is required for the first inference session.
