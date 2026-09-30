# Policy overlays

User-authored `network_policies` fragments are composed with a running
sandbox's policy and pushed with `openshell policy set`.

Overlays only touch `network_policies`. Static sections (filesystem, landlock,
and process) always come from the **live** sandbox state because the supervisor
enriches paths at startup and `policy set` rejects removed paths.

## Composition

An overlay replaces every `network_policies` entry that it names **as a whole**.
It does not recursively merge an entry with the live or baseline policy. Entries
with distinct names compose. This one rule makes an active capability explicit:
every field required by a replacement entry must be present in its overlay.

Overlay documents must contain exactly one root key, `network_policies`. The
loader rejects duplicate YAML keys, reserved policy keys beginning with `_`, and
malformed policy-entry, `endpoints`, or `binaries` shapes before it calls
OpenShell.

## Local checks

`apply.py` rejects only stable, actionable invariants:

1. Two requested overlays cannot define the same policy key.
2. An endpoint cannot contain both `access` and `rules`.
3. Two GraphQL endpoints cannot select the same `(host, effective port, path)`.

The GraphQL check prevents the known intersection problem without requiring a
GitHub endpoint, so GitLab-only and other valid baselines work. OpenShell remains
the authority for endpoint-overlap, metadata, and ambiguity validation.

## Apply and revert

`openshell`, `python3`, and PyYAML are required. Run from the repository root:

```bash
# Enable GitHub issue and PR writes.
./policy-overlays/apply.py --sandbox <sandbox-name> github-issues-prs.yaml

# Combine independent capabilities.
./policy-overlays/apply.py --sandbox <sandbox-name> github-issues-prs.yaml github-push.yaml

# Restore the configured baseline and remove every active overlay.
./policy-overlays/apply.py --sandbox <sandbox-name> --revert

# Start from the baseline, then enable exactly the named capability.
./policy-overlays/apply.py --sandbox <sandbox-name> --revert gitlab-com-issues-mrs.yaml

# Inspect the live-to-final change without applying it.
./policy-overlays/apply.py --sandbox <sandbox-name> --dry-run github-issues-prs.yaml
```

Bare names are looked up in `policy-overlays/`; the `.yaml` suffix is optional.
A path containing `/` or beginning with `.` is used as-is. Applying the same
overlay again is idempotent because it replaces the same entry.

`--revert` reads `network_policies` from the policy selected in
`.exoshell.local.toml`, or `policies/policy.yaml` when no local policy is
configured. Its diff always compares the original live state with the final
composed state.

## GitHub overlays

### `github-issues-prs.yaml`

Replaces the baseline `github_graphql` entry with query access and approved
issue/PR GraphQL mutations. It also adds narrow REST rules for `gh api` issue,
comment, pull-request, review, label, and assignee writes.

It does not allow merges, auto-merge, REST `DELETE`, destructive GraphQL
mutations, or `git push`. It scopes its REST endpoint to `gh`; use `gh api`, not
`curl`, for these writes.

### `github-push.yaml`

Allows `POST /**/git-receive-pack` on `github.com:443` for HTTPS push. The
binary scope includes Git's `/usr/lib/git-core/**` HTTPS transport helpers. It
does not grant GitHub API writes.

### `github-graphql-audit.yaml`

Debugging only: replaces `github_graphql` with `enforcement: audit` and
`access: full`. Use it to identify a blocked GraphQL operation in sandbox logs,
then restore the normal baseline or issue/PR overlay:

```bash
./policy-overlays/apply.py --sandbox <sandbox-name> --revert github-graphql-audit.yaml
# Run the blocked gh command and inspect: openshell logs <sandbox-name>
./policy-overlays/apply.py --sandbox <sandbox-name> --revert github-issues-prs.yaml
```

## GitLab.com overlays

### `gitlab-com-issues-mrs.yaml`

Replaces the complete `gitlab_com_graphql` baseline entry while retaining its
read-only GraphQL access. `glab issue` and `glab mr` write commands use REST, so
the overlay grants only the required project issue, issue-note, merge-request,
and merge-request-note `POST` and `PUT` paths. It does not allow GraphQL
mutations, deletes, approvals, merges, or push.

### `gitlab-com-push.yaml`

Allows HTTPS Git push through `POST /**/git-receive-pack` on `gitlab.com:443`.
It is separate from issue/MR authorship and includes Git's transport helpers.

For another GitLab instance, create a separate provider profile, baseline policy
key, and host-specific overlays. Do not use host substitution: independent,
named policy entries keep each instance's grants auditable.

## Adding an overlay

Repeat every field in any entry that replaces a baseline entry. Keep independent
capabilities in separate files so users can grant and revoke them independently.
Run `--dry-run` first, then validate the composed policy with `openshell policy
set --wait` on a disposable sandbox before enabling a write capability.
