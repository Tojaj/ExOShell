# Acceptance checks

This checklist is for maintainers and contributors validating a change to
ExOShell itself; daily use needs none of it.

For each agent, launch a sandbox and verify the working directory, `sandbox`
user, host-owned writes below `/workspace`, and the agent-specific state paths.
Then verify inference through each configured backend and GitHub/GitLab CLI
access. Recreate the sandbox and confirm runtime history is absent.

## Smoke tests

After recreating the sandbox, verify identity and configuration without printing
credential variables:

```bash
id -un
printf '%s\n' "$HOME" "$PWD"
command -v gh glab git
printf '%s\n' "$GH_HOST" "$GITLAB_HOST"
gh auth status --hostname github.example.com
glab auth status --hostname gitlab.example.com
git ls-remote https://github.example.com/example/project.git
git ls-remote https://gitlab.example.com/example/project.git
```

Expected results:

- The user is `sandbox`, home is `/sandbox`, and the project is below
  `/workspace`.
- API queries, clone, and fetch work at baseline.
- API mutations and Git pushes remain blocked until explicitly allowed by both
  policy and token scope.
- `openshell policy get <sandbox> --full` contains one GraphQL endpoint for
  each configured source-control host.

When a request fails, inspect `openshell logs <sandbox> --tail --source sandbox`.
Check the destination, binary path, HTTP method and path, policy enforcement,
and `credential_endpoint_mismatch`. Fix a credential endpoint mismatch in the
provider profile only when the destination is an intended credential recipient;
widening user policy alone does not change credential binding.

## Upstream references

- [OpenShell provider profiles](https://docs.nvidia.com/openshell/sandboxes/providers-v2)
- [OpenShell policy schema](https://docs.nvidia.com/openshell/reference/policy-schema)
- [OpenShell compute drivers and custom
  images](https://docs.nvidia.com/openshell/reference/sandbox-compute-drivers)
- [`sandboxes/exoshell-base/README.md`](https://github.com/Tojaj/ExOShell/blob/main/sandboxes/exoshell-base/README.md)
- [`sandboxes/local-user/README.md`](https://github.com/Tojaj/ExOShell/blob/main/sandboxes/local-user/README.md)
- [`ARCHITECTURE.md`](https://github.com/Tojaj/ExOShell/blob/main/ARCHITECTURE.md)
