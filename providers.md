# Providers

Provider profiles define reusable credential bindings, permitted endpoints, and
permitted binaries. Provider instances store the local credentials for those
profiles that require them. Import only the profiles and create only the
instances needed on a machine.

## Names and origin

ExOShell-supplied profile IDs start with `exoshell-`, display names start with
"ExOShell", and each profile carries `annotations: {exoshell-origin: ExOShell}`.
The annotation identifies the source of the definition; it does not establish
installer ownership. Profile filenames are independent of their IDs.

Use profile IDs with `provider create --type`; use instance names with the
launcher's `--provider` and TOML `providers` arrays. Suggested instance names
drop a profile's trailing `-cli`; other instance names match the profile ID.
Instance names remain configurable.

| Profile ID | Suggested instance name |
| --- | --- |
| `exoshell-codex-cli` | `exoshell-codex` |
| `exoshell-claude-code-cli` | `exoshell-claude-code` |
| `exoshell-github-cli` | `exoshell-github` |
| `exoshell-gitlab-cli` | `exoshell-gitlab` |
| `exoshell-gws-cli` | `exoshell-gws` |
| `exoshell-opencode-openai` | `exoshell-opencode-openai` |
| `exoshell-opencode-anthropic` | `exoshell-opencode-anthropic` |
| `exoshell-opencode-openrouter` | `exoshell-opencode-openrouter` |
| `exoshell-atlassian-mcp` | `exoshell-atlassian-mcp` |

Registry profiles and suggested instances share the IDs in the table below.
Their `-ro` suffix means consumption without publishing, including npm's
narrowly scoped audit requests. Authenticated private downloads can also be
read-only. `-publish` is reserved for future publishing profiles.

## Opt-in package registries

Seven independent, credential-free profiles grant package or container image
downloads and metadata lookups over HTTPS. None is attached by default or grants
publishing access:

| Profile / instance | Public endpoints | Client operations |
| --- | --- | --- |
| `exoshell-npm-registry-ro` | `registry.npmjs.org` | npm install/update, search and audit (only the two npm audit POST paths) |
| `exoshell-pypi-packages-ro` | `pypi.org`, `files.pythonhosted.org` | pip/uv indexes, metadata and downloads |
| `exoshell-go-modules-ro` | `proxy.golang.org`, `sum.golang.org` | Go proxy resolution and checksum verification |
| `exoshell-cargo-crates-ro` | `index.crates.io`, `static.crates.io`, `crates.io` | Cargo index, downloads, search and metadata |
| `exoshell-ghcr-registry-ro` | `ghcr.io`, `pkg-containers.githubusercontent.com` | Public OCI image and artifact reads by agents, `curl`, `oras`, `skopeo`, and Python tools |
| `exoshell-dockerhub-registry-ro` | `registry-1.docker.io`, `auth.docker.io`, `production.cloudfront.docker.com`, `docker-images-prod.6aa30f8b08e16409b46e0173d6de2f56.r2.cloudflarestorage.com` | Public OCI image and artifact reads by agents, `curl`, `oras`, `skopeo`, and Python tools |
| `exoshell-quay-registry-ro` | `quay.io`, `cdn.quay.io`, `cdn01.quay.io` through `cdn06.quay.io` | Public OCI image and artifact reads by agents, `curl`, `oras`, `skopeo`, and Python tools |

All seven allow GET/HEAD/OPTIONS; npm alone also allows POST to
`/-/npm/v1/security/advisories/bulk` and `/-/npm/v1/security/audits/quick`.
Publishing, login, and unrelated POST/PUT/PATCH/DELETE requests are not granted.

Import and create only the ecosystems needed by a project. For each desired
name below (for example `exoshell-npm-registry-ro`), run:

```bash
openshell provider profile lint -f provider-profiles/provider-npm-registry.yaml
openshell provider profile import -f provider-profiles/provider-npm-registry.yaml
openshell provider create --name exoshell-npm-registry-ro --type exoshell-npm-registry-ro
```

These profiles require no credentials. Do not supply a dummy credential,
`--runtime-credentials`, or `--from-existing` for them.

For PyPI, Go, Cargo, and GHCR, select the file and ID independently:

| Profile file under `provider-profiles/` | Profile ID / instance |
| --- | --- |
| `provider-pypi-packages.yaml` | `exoshell-pypi-packages-ro` |
| `provider-go-modules.yaml` | `exoshell-go-modules-ro` |
| `provider-cargo-crates.yaml` | `exoshell-cargo-crates-ro` |
| `provider-ghcr-registry.yaml` | `exoshell-ghcr-registry-ro` |

Lint/import the selected file, then create with `--name <instance> --type <id>`.
For the two additional container registries:

```bash
openshell provider profile lint -f provider-profiles/provider-dockerhub-registry.yaml
openshell provider profile import -f provider-profiles/provider-dockerhub-registry.yaml
openshell provider create --name exoshell-dockerhub-registry-ro --type exoshell-dockerhub-registry-ro

openshell provider profile lint -f provider-profiles/provider-quay-registry.yaml
openshell provider profile import -f provider-profiles/provider-quay-registry.yaml
openshell provider create --name exoshell-quay-registry-ro --type exoshell-quay-registry-ro
```

These profiles have no credential discovery. They compose with an agent's
inference provider; their names select provider *instances*, not profile files.

The `exoshell-ghcr-registry-ro` profile permits agents, `curl`, `oras`, `skopeo`, and Python
to read public GHCR tokens, image manifests, and artifacts. GHCR may redirect blob
downloads to `pkg-containers.githubusercontent.com`. Attach it when running the
base-image version checker inside an OpenShell sandbox; that checker validates
the pinned `uv` source image on GHCR. The profile does not govern image pulls
by the host's container engine. OCI repository names use ordinary slashes in
request paths, so this profile does not enable `allow_encoded_slash`; the
checker's encoded slash is in a token-request query parameter.

The `exoshell-dockerhub-registry-ro` profile permits anonymous token requests to
`auth.docker.io` and image reads from `registry-1.docker.io`, including redirects
to Docker's CloudFront and Cloudflare R2 download hosts. See the
[Docker allowlist](https://docs.docker.com/desktop/enterprise/allow-list/) and
[Docker maintainer confirmation of the R2 host](https://github.com/docker/docs/issues/21960).
The `exoshell-quay-registry-ro` profile covers `quay.io` (including its anonymous token
endpoint) and the seven exact CDN hosts listed in the
[upstream firewall documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/installation_configuration/configuring-firewall).
Both profiles use ordinary slashes in repository paths and leave
`allow_encoded_slash` disabled. Encoded slashes in token and signed-download
query parameters do not require that setting.

All three container registry profiles support the same clients and require no
login. They grant public metadata, manifests, configuration blobs, and image
layers; private image authentication is not configured. Docker Hub's anonymous
pull limits still apply. These grants control requests made inside the sandbox,
not image pulls made by the host or gateway container engine.

The base image supplies Skopeo through its distribution package. After rebuilding
the base and derived image layers, inspect a public image in a sandbox with the
matching provider attached:

```bash
# exoshell-dockerhub-registry-ro
skopeo inspect docker://docker.io/library/alpine:latest
oras manifest fetch docker.io/library/alpine:latest

# exoshell-quay-registry-ro
skopeo inspect docker://quay.io/prometheus/busybox:latest
oras manifest fetch quay.io/prometheus/busybox:latest

# exoshell-ghcr-registry-ro
skopeo inspect docker://ghcr.io/astral-sh/uv:0.12.22
```

To verify layer downloads and CDN redirects, copy one of those images to a
writable local OCI layout, for example:

```bash
skopeo copy docker://docker.io/library/alpine:latest oci:/tmp/alpine-smoke:latest
```

For repeat use, add the selected instance names to the common `providers`
array in `.exoshell.local.toml` so Codex, Claude Code, and OpenCode all get
them. For one run, repeat `--provider` for **every** desired instance, including
the inference provider: CLI options replace the complete configured list.

```bash
./run-exoshell-agent.sh --agent codex \
  --provider exoshell-codex --provider exoshell-dockerhub-registry-ro --provider exoshell-quay-registry-ro \
  . -- exec 'reply with OK'
```

Direct OpenShell launches can also attach them independently:

```bash
openshell sandbox create --from localhost/exoshell-local:latest \
  --policy policies/policy.yaml --provider exoshell-codex --provider exoshell-npm-registry-ro \
  -- codex
```

Add the workspace mount and image startup command as described in the
[image guide](sandboxes/exoshell-base/README.md) when working on a host project.
The base image supplies npm, uv/uvx and the agents; it does not install Go or
Cargo. For those clients, use an image with the tools installed and check their
kernel-resolved executable paths against the profile `binaries` list (for
example, `readlink -f "$(command -v go)"`). OpenShell matches the resolved
executable and its ancestors, not a package-manager script named in argv.
For npm, that executable is `/usr/bin/node`; for Python it may be a uv-managed
interpreter under `/sandbox/.uv/python/`.

To use an enterprise proxy, mirror, or private registry, copy the relevant
profile YAML under a new filename, change `id`, `display_name` and the endpoint
host(s) to the actual service, set origin metadata to your own source, and
lint/import/create a new instance from it.
Configure the corresponding npm, pip/uv, Go, or Cargo client to use that
endpoint separately; attaching a provider does not reconfigure the client.
Some ecosystems require separate index, download, and checksum hosts. Add only
those observed and required, and bind credentials explicitly for authenticated
registries. Review the **entire** effective sandbox policy and **all** attached
providers (for example with `openshell sandbox get <name> --policy-only`) for
grants to public registry hosts: attaching only a private clone excludes its
public counterpart only if no other layer grants it. To avoid Go's default
direct-VCS fallback, set `GOPROXY=https://proxy.golang.org` (without `,direct`)
and review `GOPRIVATE`/`GOSUMDB` for the modules in use. Git dependencies and
interpreter installers are not covered. Maven/Gradle, NuGet, RubyGems, and
Composer can have separate profiles later. See
[ADR 24](adrs/adr0024-opt-in-package-registry-providers.md).

## Provider lifecycle

Lint a profile before its first import:

```bash
openshell provider profile lint -f provider-profiles/provider-example.yaml
openshell provider profile import -f provider-profiles/provider-example.yaml
```

Profile import is create-only. To change an imported profile, export its
current resource version, copy that value into the local profile YAML, then
update the profile:

```bash
openshell provider profile export example-profile -o yaml > /tmp/example-profile.yaml
# Copy resource_version from /tmp/example-profile.yaml into the local profile.
openshell provider profile update example-profile -f provider-profiles/provider-example.yaml
```

An update applies to every instance of that profile type and reaches running
sandboxes on their next configuration sync. OpenShell rejects an update that
would make an attached sandbox's effective policy invalid.

Recreate a provider only when its type or credential environment needs to
change. Delete any sandbox that attaches it first, delete the provider, then
create the replacement. Delete and re-import a profile only when it must be
re-created rather than updated:

```bash
openshell sandbox delete <sandbox-name>
openshell provider delete <provider-name>
openshell provider profile delete <profile-id>
openshell provider profile lint -f provider-profiles/provider-example.yaml
openshell provider profile import -f provider-profiles/provider-example.yaml
openshell provider create --name <provider-name> --type <profile-id> --from-existing
```

Keep credentials out of image layers, policies, launcher configuration, and
shell scripts. Prefer `--from-existing` where the profile supports credential
discovery; it reads the required environment value from the host shell and
stores it through OpenShell.

Future installation tooling must record the objects it creates. Uninstall must
use that record and check modifications and dependencies; names and origin
annotations alone are insufficient grounds for deletion.

## Composition and policy

Do not attach providers that export the same credential environment variable to
the same sandbox. Common conflicts include Codex and OpenCode OpenAI providers
(`OPENAI_API_KEY`), Claude Code and OpenCode Anthropic providers
(`ANTHROPIC_API_KEY`), multiple GitHub providers, and multiple GitLab
providers. Use separate sandboxes when switching between instances that share a
credential environment.

Some source-control profiles require a matching GraphQL endpoint in the
sandbox policy. Policy overrides can grant narrowly scoped writes without
changing a profile. See [policy overlays](policy-overlays/README.md) for the
overlay workflow and [`CUSTOMIZATION.md`](CUSTOMIZATION.md) for custom hosts.

## Codex CLI

`exoshell-codex-cli` runs Codex with an OpenAI API key, rather than ChatGPT OAuth. It
allows unresolved provider placeholders in inference request bodies so a
credential from another provider is never substituted into a conversation sent
to OpenAI.

Do not attach it with `exoshell-opencode-openai`: both export `OPENAI_API_KEY`.

```bash
openshell provider profile lint -f provider-profiles/provider-codex-cli.yaml
openshell provider profile import -f provider-profiles/provider-codex-cli.yaml
```

```bash
openshell provider create --name exoshell-codex \
  --type exoshell-codex-cli --credential OPENAI_API_KEY
```

The custom profile is required because the built-in Codex profile injects
`CODEX_AUTH_*` credentials and cannot enable the required
`allow_uninspected_credentials` behavior. See [ADR 8](adrs/adr0008-custom-codex-provider-allow-uninspected-credentials.md).

Smoke test by launching Codex with the provider and asking it to complete a
small request:

```bash
./run-exoshell-agent.sh --agent codex --provider exoshell-codex . -- exec 'reply with OK'
```

## Claude Code CLI

`exoshell-claude-code-cli` supplies an Anthropic API key to Claude Code. Inference
request bodies can contain opaque placeholders from other providers, so the
profile preserves those placeholders until the appropriate request is made.

Do not attach it with `exoshell-opencode-anthropic`: both export `ANTHROPIC_API_KEY`.
Subscription OAuth is not supported because it requires sandbox-readable
persistent credentials.

```bash
openshell provider profile lint -f provider-profiles/provider-claude-code-cli.yaml
openshell provider profile import -f provider-profiles/provider-claude-code-cli.yaml
```

```bash
openshell provider create --name exoshell-claude-code \
  --type exoshell-claude-code-cli --credential ANTHROPIC_API_KEY
```

The provider keeps the API key behind an OpenShell placeholder rather than
placing readable credentials in Claude Code state.

Smoke test:

```bash
./run-exoshell-agent.sh --agent claude --provider exoshell-claude-code . -- \
  -p 'reply with OK'
```

## OpenCode with OpenRouter

`exoshell-opencode-openrouter` supplies an OpenRouter API key to OpenCode. It is the
default OpenCode provider in the example launcher configuration.

Do not use OpenCode's `/connect` flow. It writes readable credentials to
`~/.local/share/opencode/auth.json`; OpenCode must consume the provider-exported
placeholder instead.

```bash
openshell provider profile lint -f provider-profiles/provider-opencode-openrouter.yaml
openshell provider profile import -f provider-profiles/provider-opencode-openrouter.yaml
```

```bash
openshell provider create --name exoshell-opencode-openrouter \
  --type exoshell-opencode-openrouter --credential OPENROUTER_API_KEY
```

The profile grants OpenCode access only to OpenRouter and retains opaque
placeholders in inference request bodies.

Smoke test by starting OpenCode with a known OpenRouter model:

```bash
./run-exoshell-agent.sh --agent opencode --provider exoshell-opencode-openrouter . -- \
  --model openrouter/example
```

## OpenCode with OpenAI

`exoshell-opencode-openai` supplies an OpenAI API key to OpenCode. Use it when OpenCode
should call OpenAI directly instead of OpenRouter.

Do not attach it with `exoshell-codex`: both export `OPENAI_API_KEY`. Do not use
OpenCode's `/connect` flow because it persists readable credentials.

```bash
openshell provider profile lint -f provider-profiles/provider-opencode-openai.yaml
openshell provider profile import -f provider-profiles/provider-opencode-openai.yaml
```

```bash
openshell provider create --name exoshell-opencode-openai \
  --type exoshell-opencode-openai --credential OPENAI_API_KEY
```

The profile keeps the key provider-backed while allowing OpenCode's inference
requests to carry opaque placeholders from other integrations.

Smoke test by launching OpenCode with this provider and selecting an OpenAI
model supported by the image configuration.

## OpenCode with Anthropic

`exoshell-opencode-anthropic` supplies an Anthropic API key to OpenCode. Use it when
OpenCode should call Anthropic directly.

Do not attach it with `exoshell-claude-code`: both export `ANTHROPIC_API_KEY`. Do not
use OpenCode's `/connect` flow because it persists readable credentials.

```bash
openshell provider profile lint -f provider-profiles/provider-opencode-anthropic.yaml
openshell provider profile import -f provider-profiles/provider-opencode-anthropic.yaml
```

```bash
openshell provider create --name exoshell-opencode-anthropic \
  --type exoshell-opencode-anthropic --credential ANTHROPIC_API_KEY
```

The profile uses the same placeholder-safe inference pattern as the other
OpenCode backends.

Smoke test by launching OpenCode with this provider and selecting an Anthropic
model supported by the image configuration.

## GitHub CLI

`exoshell-github-cli` supplies `GITHUB_TOKEN` and `GH_TOKEN` to `gh` and Git-over-HTTPS
for GitHub.com. It permits read-only API access plus clone and fetch at
baseline.

Do not attach two GitHub providers that export the same credential variables.
This profile requires a policy with one `github_graphql` endpoint for
`api.github.com`; without it, GraphQL requests are denied. Do not duplicate that
endpoint in a policy override.

```bash
openshell provider profile lint -f provider-profiles/provider-github-cli.yaml
openshell provider profile import -f provider-profiles/provider-github-cli.yaml
```

```bash
export GITHUB_TOKEN="$(gh auth token)"
openshell provider create --name exoshell-github --type exoshell-github-cli --from-existing
unset GITHUB_TOKEN
```

The custom profile replaces the built-in `github` profile because it omits
`/graphql`. Keeping that endpoint solely in user policy allows a policy override
to grant approved GraphQL mutations; a provider-owned read-only GraphQL endpoint
could only narrow such an override. See [ADR 1](adrs/adr0001-graphql-endpoint-declared-once-in-user-policy.md).

Smoke test inside a sandbox that attaches `exoshell-github`:

```bash
gh repo list
gh auth status --hostname github.com
git ls-remote https://github.com/<owner>/<repository>.git
```

## GitLab.com CLI

`exoshell-gitlab-cli` supplies `GITLAB_TOKEN` and `GLAB_TOKEN` to `glab` and Git-over-
HTTPS for GitLab.com. It permits read-only REST API access plus clone and fetch
at baseline.

Attach at most one GitLab provider to a sandbox because GitLab profiles share
`GITLAB_TOKEN` and `GLAB_TOKEN`. This profile requires a policy with one
`gitlab_com_graphql` endpoint for `gitlab.com`; do not duplicate that endpoint
in a policy override. A different GitLab host requires its own profile YAML,
profile ID, policy entry, and provider instance.

```bash
openshell provider profile lint -f provider-profiles/provider-gitlab-cli.yaml
openshell provider profile import -f provider-profiles/provider-gitlab-cli.yaml
```

```bash
# Get token from:
glab auth status --hostname gitlab.com --show-token
# Put the token into env var:
export GITLAB_TOKEN="<TOKEN>"
openshell provider create --name exoshell-gitlab --type exoshell-gitlab-cli --from-existing
unset GITLAB_TOKEN
```

The profile omits `/api/graphql` for the same policy-composition reason as the
GitHub profile. `glab` issue and merge-request commands use REST; GraphQL is
used by `glab api graphql` and `glab workitems list`. See [ADR 9](adrs/adr0009-gitlab-provider-graphql-in-user-policy.md).

Configure `gitlab_host = "gitlab.com"` in `.exoshell.local.toml` when the
launcher must select this host. Remove any equal-specificity GitLab.com audit
entry from the active policy after attaching the provider, because it conflicts
with the provider's enforce endpoint.

Smoke test inside a sandbox that attaches `exoshell-gitlab`:

```bash
glab auth status --hostname gitlab.com
git ls-remote https://gitlab.com/<namespace>/<project>.git
```

## Google Workspace OAuth

`exoshell-gws-cli` provides OAuth credentials to the Google Workspace CLI. The
sandbox receives placeholders for the client ID, client secret, and refresh
token; OpenShell substitutes the secret values only in OAuth token request
bodies. GWS 0.22.5 uses `accounts.google.com/o/oauth2/token` through
`yup-oauth2` by default, and `oauth2.googleapis.com/token` when it selects
its proxy-aware refresh path. The profile covers both.

Do not mount the host GWS configuration into the sandbox. When using this
provider, the image helper automatically writes placeholder credentials into
the launcher's `/tmp/gws` tmpfs when all three credential environment values
are non-empty. A partial set fails startup; an absent set skips initialization.
Refresh or replace the provider after reauthorizing on the host with changed scopes.

```bash
openshell provider profile lint -f provider-profiles/provider-gws-cli.yaml
openshell provider profile import -f provider-profiles/provider-gws-cli.yaml
```

```bash
GWS_CREDS="$(gws auth export --unmasked)"
openshell provider create --name exoshell-gws --type exoshell-gws-cli \
  --credential "GWS_CLIENT_ID=$(jq -r .client_id <<<"$GWS_CREDS")" \
  --credential "GWS_CLIENT_SECRET=$(jq -r .client_secret <<<"$GWS_CREDS")" \
  --credential "GWS_REFRESH_TOKEN=$(jq -r .refresh_token <<<"$GWS_CREDS")"
unset GWS_CREDS
```

The provider uses request-body credential rewriting because the GWS CLI ignores
environment-variable authentication while its encrypted credentials file is
present. See [ADR 2](adrs/adr0002-gws-credentials-via-provider-body-rewrite.md).

Smoke test inside a sandbox launched with `--provider exoshell-gws`:

```bash
gws drive files list --params '{"pageSize":1,"fields":"files(id),nextPageToken"}'
```

`gws auth status` may display placeholder values and can report a valid token
without testing a token exchange. Do not print the provider credential
environment variables.

## Atlassian Rovo MCP

`exoshell-atlassian-mcp` supplies a short-lived OAuth 2.1 Bearer token to the Atlassian
Rovo MCP endpoint used by the image-provided Codex, Claude Code, and OpenCode
configurations. The refresh token remains on the host.

Atlassian MCP is disabled in fresh images. The launcher's `exoshell-agent`
startup helper enables it only when `ATLASSIAN_MCP_BEARER_TOKEN` is non-empty
in the agent's environment. OpenShell supplies an opaque credential placeholder
when the provider is attached; the helper does not inspect or persist the token.
Provider instance names are arbitrary: a separately named instance using the
same credential environment key works too. Missing or empty credentials disable
the integration without an Atlassian connection attempt.

The helper controls the built-in `atlassian` entry at each startup, overriding
conflicting enable/disable settings. Other MCP servers and agent settings are
preserved. Codex uses a command-line override, OpenCode merges an inline runtime
override, and Claude updates its private user configuration and per-project
disabled-server list. Claude state lives in `/sandbox/.claude/.claude.json`
through `CLAUDE_CONFIG_DIR`, within the existing writable filesystem policy.
Bare client invocations bypass this startup decision; use the launcher or
`exoshell-agent` for automatic behavior. Client managed policy and explicit
configuration-source restrictions still apply; this is startup configuration,
not a security boundary.

Attach this provider only to Codex, Claude Code, or OpenCode sandboxes.
Synchronize it before starting a new sandbox or agent process because access
tokens expire in about one hour. Restart the agent after changing its
configuration because MCP configuration is loaded only at startup.
After attaching, detaching, or updating a provider on an existing sandbox, wait
for OpenShell to apply the change, then invoke the helper in a fresh OpenShell
exec or SSH session. An already-running shell retains its old credential
environment. A non-empty placeholder does not establish token validity.

```bash
openshell provider profile lint -f provider-profiles/provider-atlassian-mcp.yaml
openshell provider profile import -f provider-profiles/provider-atlassian-mcp.yaml
```

```bash
./scripts/atlassian-mcp-oauth.sh sync
```

`sync` creates `exoshell-atlassian-mcp` from the imported profile when needed, opens a
browser for authorization when host-side OAuth state is unavailable, and
otherwise refreshes the provider directly. It stores per-provider client and
refresh-token state in `~/.config/openshell/atlassian-mcp-oauth.json`, never the
access token. Use `--provider <name>` to manage a separately named instance.
To revoke access and remove the default instance:

```bash
./scripts/atlassian-mcp-oauth.sh revoke --provider exoshell-atlassian-mcp
openshell provider delete exoshell-atlassian-mcp
```

The provider uses a Bearer token instead of request-body rewriting because
Atlassian rotates refresh tokens. See [ADR 17](adrs/adr0017-atlassian-mcp-oauth-bearer.md).

Smoke tests in a newly started sandbox:

```bash
# Codex
exoshell-agent "$PWD" -- codex mcp list

# Claude Code
exoshell-agent "$PWD" -- claude mcp list

# OpenCode
exoshell-agent "$PWD" -- opencode mcp list
```

With a synchronized provider attached, confirm that Atlassian is enabled, then
make a read-only MCP request through the selected agent. Repeat without the
provider: Codex and OpenCode should show it disabled; Claude should omit its
image-provided entry. A project-defined Claude entry with the same name is
disabled for that project instead. No Atlassian request should be attempted.
