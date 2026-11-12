# Troubleshooting

Start with `./run-exoshell-agent.sh --verbose /path/to/project` on the host.
It reports the selected configuration and effective paths before provisioning.
For a retained sandbox, inspect its logs:

```bash
openshell sandbox list --selector managed-by=exoshell
openshell logs <sandbox-name> --tail --source sandbox
openshell policy get <sandbox-name> --full
```

## No policy selected or configuration not found

Pass `--policy policies/policy.yaml` from the checkout, or set `policy` in the
selected TOML file. The launcher does not discover configuration beside itself
or inside the positional project unless that is also the caller's current
directory. Use `--config PATH` to select it explicitly.

`--no-policy` delegates to OpenShell, which may choose an environment or image
policy. See [configuration](../guide/configuration.md).

## Local image unavailable or project not writable

Run `./build.sh` on the gateway host. The local ownership image is needed in
addition to the gateway's `userns = "keep-id"` setting. Check that the configured
image exists in that host's rootless Podman image store.

Inside the sandbox, `id -un` should report `sandbox`, and the selected project
should be below `/workspace`. See [image customization](../customize/images.md).

## A file moved into the project is inaccessible on SELinux

A file moved or renamed into a mounted project can retain its old SELinux label.
On the **host**, from the project directory, run:

```bash
chcon --reference=. path/to/file
```

If unsure, compare host-side `ls -ldZ .` and `ls -lZ path/to/file`.
Changing Unix permissions does not repair a label mismatch.

## Package downloads or requests are denied

Attach the appropriate [registry provider](../integrations/registries.md).
Having npm or uv installed does not grant registry access. Explicit `--provider`
options replace the full configured list, so include the inference provider too.

For other failures, check the destination, resolved binary, method, and path
against the effective policy. A `credential_endpoint_mismatch` must be resolved
in the owning provider profile for an intended recipient; widening user policy
alone does not widen the credential binding.

See [custom policies](../customize/policies.md) and
[provider lifecycle](../integrations/index.md#provider-lifecycle).

## Inference fails after changing a provider

Start a fresh session so it receives the current provider placeholders and
startup configuration. Verify the CLI, gateway, and supervisor versions match.
Do not attach providers exporting the same credential variable together. See
[inference providers](../integrations/inference.md) for backend-specific checks.

## Histories or credentials disappeared after exit

This is the default lifecycle: agent state belongs to the disposable container.
Mounted project edits survive. Use `--keep` for investigation and delete the
sandbox afterward; see [sessions and credentials](../guide/sessions.md).
