# Upgrade ExOShell to OpenShell v0.1.5

OpenShell v0.1.5 is the minimum supported release. This migration covers the
rootless Podman setup and the changes since v0.1.2. It does not require a
launcher architecture, policy schema, or provider credential migration.

## Prepare the host

Preserve the gateway's existing configuration, credential storage, and keys.
Keep local configuration and old images until acceptance passes. Finish active
sessions before restarting the gateway; runtime state in disposable sandboxes
is not persistent storage.

Upgrade the installed CLI and gateway through your existing installation
method. Updating the OpenShell source checkout alone does not update either.
After restarting, verify both versions and gateway authentication:

```bash
openshell --version
openshell status
```

Remove custom `supervisor_image` settings used only for private CA trust and
runtime-image environment overrides that still pin an old release. Fresh
sandboxes must use the stock version-matched supervisor. Preserve the existing
Podman bind-mount, driver-config, resource-admission, and `keep-id` settings;
the local-identity image layer remains necessary.

For private PKI, stage a gateway-readable PEM on the gateway host **before**
restarting, then set Podman's `additional_ca_bundle` to its absolute path.
This augments public roots in both supervisor and workload trust bundles.
Malformed or unreadable bundles can prevent gateway startup. Follow
[customization instructions](../CUSTOMIZATION.md#private-ca-for-inspected-podman-https-egress);
private certificate sources belong in the customization repository.

Keep polling, the release default. Optional
`[openshell.gateway] config_delivery_mode = "push"` can reduce live update
latency but is not required; the overlay helper retains `--wait`.

## Update profiles and launch fresh sandboxes

The five inference profiles no longer set `allow_uninspected_credentials`.
Unknown literals and valid issued placeholders pass as unchanged body text
through OpenShell's native classifier. Invalid or unavailable references can
still fail. This upstream fix predates v0.1.2; the old ExOShell exception was
retained unnecessarily. Inference body rewriting remains disabled. Custom
profile IDs, credentials, and binary selectors are unchanged.

Lint each changed profile with `openshell provider profile lint -f PATH`.
For existing imported profiles, use the documented
[resource-version update procedure](../providers.md#provider-lifecycle)
rather than create-only import. Export profiles to temporary files, carry their
resource versions into temporary copies of the updated YAML, and update those
copies. Do not commit gateway resource versions or recreate credentials just
for this change. Remove the same exception from copied custom `opencode_site`
policies, matching the public baseline.

Build the workload and local-identity layers using `./build.sh`, or the
customization repository's build against this public checkout. Launch fresh
sandboxes with the updated selected policy. Existing sessions do not gain
policy-source metadata automatically.

The launcher now records `exoshell.policy-source-file` as sandbox metadata.
Overlay `--revert` uses its current contents unless `--base-file` overrides it.
Older sandboxes, `--no-policy` launches, and unavailable recorded files require
an explicit baseline; there is no checkout-config fallback. See the
[overlay guide](../policy-overlays/README.md#apply-and-revert).

## Acceptance on the gateway host

- Run `python3 -m unittest discover -s tests -v` in the public checkout and
  downstream tests against that checkout.
- Launch disposable sandboxes with the public and customized policies. Confirm
  `openshell sandbox get NAME -o json` records the selected absolute policy path.
- For each configured agent/backend, test an unknown synthetic placeholder and
  valid issued same-provider and foreign-provider placeholders in conversation
  history, followed by another prompt. Never print actual credentials. A
  controlled test endpoint with dummy credentials can verify that body text
  stays unchanged while authentication headers resolve independently.
- Verify inspected public and private-CA HTTPS with certificate verification
  enabled, plus forge access and configured MCP integrations.
- Apply an overlay and revert from an unrelated working directory. Confirm
  temporary network grants disappear and live static policy remains intact.
  Check an unannotated sandbox requires `--base-file`.
- Verify host-owned writes, user identity, imported skills, `--no-share`, default
  cleanup, and explicit `--keep` behavior.
- Record the new public commit in the customization repository only after the
  changes are committed and compatibility checks pass.

## Other release notes

No OCSF collector or snap-service configuration is maintained in ExOShell.
Operators using them must account for these upstream changes:

- Supervisor files now use `openshell-ocsf.YYYY-MM-DD.jsonl`. Update collector
  patterns from `.log` to `.jsonl` and collect old history before upgrading;
  old files are not migrated and may be cleaned up.
- For direct snap installs or previously global user-service enablement, follow
  upstream's per-user gateway migration. Disable global enablement once with
  `sudo systemctl disable --global snap.openshell.user-gateway.service`, then
  enable it for the intended account with
  `systemctl --user enable --now snap.openshell.user-gateway.service`.

Kubernetes metadata allowlists, Go SDK creation options, and external-driver
bootstrap changes do not apply to this Podman CLI integration. New stable
placeholders and `--env-from` do not require changes to ExOShell's existing
startup and non-secret environment arguments.

Sources: [v0.1.3](https://github.com/NVIDIA/OpenShell/releases/tag/v0.1.3),
[v0.1.4](https://github.com/NVIDIA/OpenShell/releases/tag/v0.1.4),
[v0.1.5](https://github.com/NVIDIA/OpenShell/releases/tag/v0.1.5),
[placeholder fix](https://github.com/NVIDIA/OpenShell/pull/3246).
