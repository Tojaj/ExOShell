# Customizing this project

This repository is intended to be adapted to local tools, policies, and source
control services. Keep machine-specific values in `.exoshell.local.toml`, keep
credentials in OpenShell providers, and put only non-secret configuration in
images and committed YAML files.

The main extension points are:

| Need | Extension point |
|---|---|
| Additional CLIs, workload CA certificates, or managed agent defaults | [Derived sandbox image](images.md) |
| Private CA for inspected Podman HTTPS egress | [Gateway host PEM file and Podman `additional_ca_bundle`](images.md#private-ca-for-inspected-podman-https-egress) |
| Filesystem and network access | [Sandbox policy](policies.md) |
| A temporary extra capability, such as opening a pull request | [Policy overlay](overlays.md) |
| Credential injection and provider-owned endpoint access | [Provider profile and provider instance](providers.md) |
| Machine paths, selected image, policy, providers, and starting model/effort | [`.exoshell.local.toml`](../guide/configuration.md) |

Use reserved example domains such as `github.example.com` and
`gitlab.example.com` while preparing changes for publication. Never commit
tokens, authenticated CLI configuration, private keys, kubeconfigs, or files
copied from a host home directory.

## Separate customization repository

Keep site-specific profiles, policies, image layers, and model selections in a
separate repository when their contents should not be published. Consume an
explicit upstream checkout path instead of copying or modifying the launcher.
Record the upstream version tested by the customization repository.

For example, with public sources in `../ExOShell` and configuration in the
current customization repository:

```bash
../ExOShell/run-exoshell-agent.sh --config "$PWD/.exoshell.local.toml" /path/to/project
../ExOShell/policy-overlays/apply.py --sandbox <sandbox-name> \
  --base-file "$PWD/policies/policy-local.yaml" --revert \
  "$PWD/policy-overlays/example-issues.yaml"
```

TOML file paths resolve relative to that file, so `policy =
"policies/policy-local.yaml"` can stay within the customization repository.
The [overlay helper](overlays.md) uses the sandbox's recorded policy source for `--revert`.
Supply `--base-file` to override it or for an unannotated sandbox. The annotation
is an absolute path on the launching host, so another host needs its own
explicit baseline. It records provenance, not a copy of the file.

For image builds, build the public base first, then the organization-specific
workload, and finally use the upstream local-user build script to remap identity.
Configure private supervisor trust through the gateway's `additional_ca_bundle`;
no custom supervisor image is needed. Record the reviewed public revision only
after downstream compatibility checks pass.

See [ADR-0027](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0027-separate-customization-repository.md).
