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

Registry profiles and suggested instances share the IDs in the [registry table](registries.md).
Their `-ro` suffix means consumption without publishing, including npm's
narrowly scoped audit requests. Authenticated private downloads can also be
read-only. `-publish` is reserved for future publishing profiles.

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
changing a profile. See [policy overlays](https://github.com/Tojaj/ExOShell/blob/main/policy-overlays/README.md) for the
overlay workflow and [customization](../customize/index.md) for custom hosts.

## Startup and package access

GWS initialization is automatic when an attached provider supplies non-empty
`GWS_CLIENT_ID`, `GWS_CLIENT_SECRET`, and `GWS_REFRESH_TOKEN` values. Remove
the former `gws` key from local TOML files and `--gws`/`--no-gws` from launcher
commands; these options are no longer accepted. Omit the GWS provider to skip
provider-backed initialization. The launcher always mounts `/tmp/gws` as tmpfs
so a provider can also be attached later, followed by a fresh helper launch.

Do not attach inference providers that export the same variable to one
sandbox—for example the Codex OpenAI and OpenCode OpenAI profiles both export
`OPENAI_API_KEY`.

Public npm, PyPI, Go module, and Cargo registry access is opt-in through
independent, credential-free [package registry providers](registries.md#opt-in-package-registries).
In particular, `uvx`/pip dependency downloads (including Python MCP server
installation) require the `exoshell-pypi-packages-ro` instance; merely having uv in
the image does not grant PyPI access.
