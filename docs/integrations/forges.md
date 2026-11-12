# GitHub and GitLab

*Run these commands on the gateway host, from your ExOShell checkout: the paths
are relative to it. Blocks marked as sandbox commands run inside a sandbox.*

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
could only narrow such an override. See [ADR 1](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0001-graphql-endpoint-declared-once-in-user-policy.md).

Smoke test inside a sandbox that attaches `exoshell-github`:

```bash
# inside the sandbox
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
used by `glab api graphql` and `glab workitems list`. See [ADR 9](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0009-gitlab-provider-graphql-in-user-policy.md).

Configure `gitlab_host = "gitlab.com"` in `.exoshell.local.toml` when the
launcher must select this host. Remove any equal-specificity GitLab.com audit
entry from the active policy after attaching the provider, because it conflicts
with the provider's enforce endpoint.

Smoke test inside a sandbox that attaches `exoshell-gitlab`:

```bash
# inside the sandbox
glab auth status --hostname gitlab.com
git ls-remote https://gitlab.com/<namespace>/<project>.git
```

## Allow writes for a session

Both profiles are read-only at baseline: API queries, clone, and fetch work,
while issue and pull/merge-request writes and `git push` are denied. To let an
agent open a pull request or push a branch, apply a
[policy overlay](../customize/overlays.md) to the running sandbox and revert it
when the task is done.
