# Create a custom policy

Copy [`policies/policy.yaml`](https://github.com/Tojaj/ExOShell/blob/main/policies/policy.yaml) and make the smallest
changes needed for the local environment:

```bash
cp policies/policy.yaml policies/policy-local.yaml
```

Then select it in `.exoshell.local.toml`:

```toml
policy = "policies/policy-local.yaml"
```

Decide whether the derived policy is safe to commit. Hostnames can reveal
internal infrastructure even when the file contains no credentials. Keep a
site-specific policy outside a public branch when its endpoint inventory is
sensitive.

## Policy sections

- `filesystem_policy` lists readable and writable container paths. Paths not
  admitted by the effective Landlock policy are inaccessible.
- `landlock` controls whether missing paths degrade gracefully or fail sandbox
  startup.
- `process` should remain `sandbox` when using this project's images.
- `network_policies` pair destination endpoints with the exact binaries allowed
  to reach them.

Filesystem, Landlock, and process settings become static after sandbox startup.
Network policy can be hot-reloaded.

This example adds read-only API access for a tool installed in the custom
image:

```yaml
network_policies:
  example_service:
    name: example-service
    endpoints:
      - host: api.example.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-only
    binaries:
      - { path: /usr/local/bin/example-cli }
```

!!! warning "`audit` permits the traffic it records"
    Prefer `enforcement: enforce` for known behavior. `audit` is useful while
    discovering required endpoints, but it allows the requests it logs and must
    not become a permanent substitute for scoped rules.

## Composition rules

A sandbox's effective policy combines this file with every attached provider
profile. Those layers must not contradict each other:

- Attached provider profiles add `_provider_*` entries to the effective
  policy. Do not duplicate those broad host entries in the user policy.
- Equal-specificity entries for the same host and port must agree on protocol
  and enforcement. In particular, an `audit` endpoint can conflict with an
  attached provider's `enforce` endpoint.
- `access` and `rules` are mutually exclusive on one endpoint.
- A policy allow does not widen a provider credential's endpoint binding. A
  custom host must also appear in the provider profile that owns its token.
- Binary paths are security boundaries. Confirm the executable's actual path
  inside the image with `command -v` and, for wrappers, inspect the resolved
  executable as well.

## GraphQL endpoints

The source-control profiles in this repository deliberately omit GraphQL
endpoints. Declare each GraphQL endpoint exactly once in the user policy so a
policy overlay can replace the baseline rule instead of intersecting with a
provider-owned rule.

For self-hosted GitHub and GitLab instances:

```yaml
network_policies:
  github_enterprise_graphql:
    name: github-enterprise-graphql
    endpoints:
      - host: github.example.com
        port: 443
        path: /api/graphql
        protocol: graphql
        access: read-only
        enforcement: enforce
    binaries:
      - { path: /usr/bin/gh }
      - { path: /usr/local/bin/gh }

  gitlab_enterprise_graphql:
    name: gitlab-enterprise-graphql
    endpoints:
      - host: gitlab.example.com
        port: 443
        path: /api/graphql
        protocol: graphql
        access: read-only
        enforcement: enforce
    binaries:
      - { path: /usr/bin/glab }
      - { path: /usr/local/bin/glab }
```

`read-only` permits GraphQL queries, not mutations. Add narrowly scoped policy
overlays for required mutations; do not add a second matching GraphQL endpoint.
See [policy overlays](overlays.md) for this project's overlay workflow.

## Iterate and verify

Create a sandbox with the policy, inspect denied requests, and update only the
required rules. Launch with `--keep` so the sandbox survives the agent exiting,
because the default lifecycle deletes it along with its logs:

```bash
./run-exoshell-agent.sh --keep --policy policies/policy-local.yaml .
```

OpenShell assigns the sandbox name, so look it up after the launch and use it in
the inspection commands:

```bash
openshell sandbox list --selector managed-by=exoshell
openshell logs <sandbox-name> --tail --source sandbox
openshell policy get <sandbox-name> --full
```

For a running sandbox, network-only changes can be applied without recreation:

```bash
openshell policy get <sandbox-name> --base > /tmp/current-policy.yaml
# Remove the metadata header above the YAML document marker before reuse.
openshell policy set <sandbox-name> --policy /tmp/current-policy.yaml --wait
```

Recreate the sandbox after changing static policy sections or after adding the
first `protocol: tcp` endpoint. Delete each retained sandbox when the
investigation is finished:

```bash
openshell sandbox delete <sandbox-name>
```

To grant a capability temporarily on a running sandbox instead of editing the
baseline, see [policy overlays](overlays.md).
