# Rotate provider secrets

Use the rotation helper to store a replacement token or API key in an existing
OpenShell provider instance. Run it in an interactive terminal on the gateway
host with Python 3.11 or newer, PyYAML, and the OpenShell CLI configured for the
intended gateway and workspace.

```bash
./scripts/rotate-provider-secrets.py
```

The menu shows instances whose profile IDs match definitions in the checkout.
Choose the instance by name and paste each replacement at its hidden prompt.
Press Enter to skip a credential. For example, a GitHub token prompt updates
both aliases if the instance stores both. For Google Workspace, you can skip
the client ID and client secret and replace just the refresh token.

Review the instance name and credential keys, then enter `y` to save. The
helper sends the values to OpenShell in the update command's environment.
Press Enter at the confirmation prompt to discard the replacements, or press
Ctrl+C before confirming to exit. After each update, the menu lets you choose
another instance or press Enter to finish.

The helper preserves existing credential expiry metadata. If a key has a
recorded expiry, use OpenShell's `--credential-expires-at` to set the new expiry
or clear it. The success message confirms that the update command completed.
To check activation in a running sandbox, use
`openshell sandbox provider status <sandbox-name> <provider-name>`.
