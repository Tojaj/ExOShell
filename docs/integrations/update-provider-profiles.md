# Update provider profiles

After updating your ExOShell checkout, use
[`scripts/update-provider-profiles.sh`](https://github.com/Tojaj/ExOShell/blob/main/scripts/update-provider-profiles.sh)
to apply its profile changes to profiles already imported into your gateway.
Pulling repository changes does not update those live definitions, and
`openshell provider profile import` is create-only.

## Prerequisites

Run the script **on the gateway host, from the root of your ExOShell checkout**.
It requires Bash, the `openshell` CLI configured for the intended gateway, and
`python3` with PyYAML installed.

The profiles must already be imported. For a new integration, follow its
[setup guide](index.md) to import the profile and create a provider instance
first.

## Choose profiles to update

Refresh every imported profile that has a matching definition under this
checkout's `provider-profiles/` directory:

```bash
./scripts/update-provider-profiles.sh
```

Or select one or more **profile IDs**, rather than provider instance names or
YAML filenames:

```bash
./scripts/update-provider-profiles.sh exoshell-github-cli
./scripts/update-provider-profiles.sh exoshell-npm-registry-ro exoshell-go-modules-ro
```

For each proposed change, the script shows a diff and asks for confirmation.
Enter `y` to apply it; pressing Enter skips that profile. Profiles without a
matching local definition are skipped. An explicitly selected profile with a
local definition must also exist in the gateway, or its export fails.

Use `--yes` (or `-y`) to skip confirmation prompts; diffs are still printed:

```bash
./scripts/update-provider-profiles.sh --yes exoshell-npm-registry-ro
```

## What changes

The script exports each live profile and replaces its `description`,
`endpoints`, and `binaries` with the corresponding fields from the checkout.
These fields are replaced in full, so review the diff for local gateway edits
that would be overwritten. Other live fields, including `resource_version`,
deployment metadata, credential definitions, and discovery settings, are
preserved. The script runs lint before submitting the update and tolerates
the expected diagnostic that the profile ID already exists.

This refresh keeps existing provider instances and their stored credentials.
Changes to other profile fields need a
[manual export, edit, and update](../customize/providers.md#lint-and-import-profiles).
Profiles maintained in a separate customization repository need their own
update workflow unless matching definitions are present in the working
directory's `provider-profiles/`.

Updates affect **every provider instance of that profile type**, including
attached running sandboxes on their next configuration sync. OpenShell rejects
updates that would make an attached sandbox's effective policy invalid.
Profiles are updated sequentially; if a later update fails, earlier successful
updates remain applied.

After updating, inspect an affected sandbox's effective policy:

```bash
openshell policy get <sandbox-name> --full
```
