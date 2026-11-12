# Grant writes with policy overlays

A **policy overlay** is a small YAML fragment of `network_policies` that is
composed with a *running* sandbox's policy and pushed to it with
`openshell policy set`. Overlays make one extra capability active for one
sandbox, without editing the baseline policy and without recreating the
sandbox.

Use an overlay when the baseline's read-only grants are not enough for the task
at hand, for example to let an agent open a pull request or push a branch. The
baseline policy and the source-control provider profiles deliberately permit
API reads, clone, and fetch only; see [GitHub and GitLab](../integrations/forges.md).

Overlays change only `network_policies`. Filesystem, Landlock, and process
settings always come from the live sandbox, because they become static once the
sandbox starts. Changing those still requires a new sandbox with an edited
[policy](policies.md).

## Available overlays

Each file under `policy-overlays/` grants one capability, so capabilities can be
granted and revoked independently:

| Overlay | Grants | Does not grant |
| --- | --- | --- |
| `github-issues-prs.yaml` | GraphQL and `gh api` REST writes for issues, comments, pull requests, reviews, labels, assignees | Merges, auto-merge, REST `DELETE`, destructive mutations, `git push` |
| `github-push.yaml` | HTTPS `git push` to `github.com` | GitHub API writes |
| `github-graphql-audit.yaml` | Debugging only: switches the GitHub GraphQL entry to `audit` so blocked operations appear in the logs | Anything intended for routine use |
| `gitlab-com-issues-mrs.yaml` | `glab` REST writes for issues, notes, merge requests, and MR notes on `gitlab.com` | GraphQL mutations, deletes, approvals, merges, push |
| `gitlab-com-push.yaml` | HTTPS `git push` to `gitlab.com` | Issue or MR authorship |
| `ubuntu-updates.yaml` | APT reads from `archive.ubuntu.com` and `security.ubuntu.com` | Filesystem permissions needed to install packages |

`github-issues-prs.yaml` scopes its REST endpoint to `gh`, so use `gh api`
rather than `curl` for those writes.

## Apply and revert

The helper needs `openshell`, `python3`, and PyYAML on the gateway host. Launch
the sandbox with `--keep` so it outlives the agent, look up the name OpenShell
assigned to it, then apply overlays from your ExOShell checkout:

```bash
./run-exoshell-agent.sh --keep --policy policies/policy.yaml /path/to/project
openshell sandbox list --selector managed-by=exoshell
```

```bash
# Enable GitHub issue and PR writes.
./policy-overlays/apply.py --sandbox <sandbox-name> github-issues-prs.yaml

# Combine independent capabilities.
./policy-overlays/apply.py --sandbox <sandbox-name> github-issues-prs.yaml github-push.yaml

# Inspect the live-to-final change without applying it.
./policy-overlays/apply.py --sandbox <sandbox-name> --dry-run github-issues-prs.yaml

# Restore this sandbox's recorded baseline and remove every active overlay.
./policy-overlays/apply.py --sandbox <sandbox-name> --revert

# Start from the baseline, then enable exactly the named capability.
./policy-overlays/apply.py --sandbox <sandbox-name> --revert github-issues-prs.yaml
```

Bare names are looked up in `policy-overlays/` and the `.yaml` suffix is
optional. Applying the same overlay twice is idempotent. Delete the retained
sandbox when the work is finished; overlays live only as long as it does.

!!! warning "An overlay widens what the agent can do"
    A granted capability stays active for the whole session, for every command
    the agent runs. Grant the narrowest overlay that unblocks the task, prefer
    `--dry-run` first, and revert when the task is done.

## Where `--revert` finds the baseline

`--revert` reads `network_policies` from an explicit `--base-file`, or otherwise
from the sandbox annotation `exoshell.policy-source-file`. The launcher records
the resolved absolute policy path there when it creates a sandbox with a
selected policy, so revert works from any working directory. It reads the file's
current contents rather than a creation-time snapshot.

Sandboxes created before that feature, direct OpenShell launches, and
`--no-policy` launches carry no annotation and need an explicit baseline:

```bash
./policy-overlays/apply.py --sandbox <sandbox-name> --revert --base-file ./policies/policy.yaml
```

The helper fails with an instruction to supply `--base-file` rather than
guessing from launcher configuration. Supply one explicitly after moving the
policy file or when managing a sandbox from another host, because the
annotation records a path on the launching host.

## Write your own

An overlay replaces every `network_policies` entry it names **as a whole**; it
does not merge recursively with the live or baseline entry. Repeat every field
the replacement entry needs. Entries with distinct names compose. For another
GitLab or GitHub Enterprise instance, add a separate provider profile, baseline
policy key, and host-specific overlays instead of substituting hostnames, so
each instance's grants stay auditable.

For the complete composition rules, local validation checks, and instructions
for contributing an overlay, see
[`policy-overlays/README.md`](https://github.com/Tojaj/ExOShell/blob/main/policy-overlays/README.md)
and [ADR-0044](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0044-sandbox-policy-source-annotations.md).
