# Providers

Provider profiles define reusable credential bindings, permitted endpoints, and
permitted binaries. Provider instances store the local credentials for those
profiles that require them. Import only the profiles and create only the
instances needed on a machine.

This page covers the rules that apply to every provider. For the setup steps of
a specific service, go straight to its page:

| Integration | Use it for |
| --- | --- |
| [Inference providers](inference.md) | The API key that runs Codex, Claude Code, or OpenCode |
| [GitHub and GitLab](forges.md) | `gh`, `glab`, and Git over HTTPS |
| [Opt-in package registries](registries.md) | npm, PyPI, Go, Cargo, APT, and container image downloads |
| [Google Workspace OAuth](google-workspace.md) | The `gws` CLI |
| [Atlassian Rovo MCP](atlassian.md) | Jira and Confluence through MCP |
| [Tavily web search](web-search.md) | Agent web research |

Run the commands on these pages **on the gateway host, from your ExOShell
checkout**: they use paths relative to it, such as `provider-profiles/`.

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
| `exoshell-tavily-search` | `exoshell-tavily-search` |

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

## Composition and policy

!!! warning "Never attach two providers that export the same variable"
    Do not attach providers that export the same credential environment
    variable to the same sandbox. Common conflicts include Codex and OpenCode
    OpenAI providers (`OPENAI_API_KEY`), Claude Code and OpenCode Anthropic
    providers (`ANTHROPIC_API_KEY`), multiple GitHub providers, and multiple
    GitLab providers. Use separate sandboxes when switching between instances
    that share a credential environment.

Some source-control profiles require a matching GraphQL endpoint in the
sandbox policy. Policy overlays can grant narrowly scoped writes without
changing a profile. See [policy overlays](../customize/overlays.md) for that
workflow and [customization](../customize/index.md) for custom hosts.
