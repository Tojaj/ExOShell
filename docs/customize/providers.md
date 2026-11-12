# Create custom source-control providers

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
  - /usr/lib/node_modules/@opencode/**
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
  - /usr/lib/node_modules/@opencode/**
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
