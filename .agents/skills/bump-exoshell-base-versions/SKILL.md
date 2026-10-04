---
name: bump-exoshell-base-versions
description: Check and interactively update pinned CLI versions in the ExOShell base Dockerfile. Use for version reviews or bump requests for sandboxes/exoshell-base.
---

# Bump ExOShell base versions

Follow [ADR 0011](../../../adrs/adr0011-pin-sandbox-cli-versions.md): present release choices before editing pins. Do not infer an upgrade from a failed lookup or failed asset check.

Run the read-only checker from the repository root:

```bash
python3 .agents/skills/bump-exoshell-base-versions/scripts/check_versions.py
```

When running inside an OpenShell sandbox, attach the optional `exoshell-ghcr-registry-ro`
provider to let the checker validate the `uv` source image on GHCR.

Use `--lag 1` or `--lag 2` when the user wants a cooling-off window. The checker reports every version ARG in `sandboxes/exoshell-base/Dockerfile`, including `AST_GREP_VERSION`, with its pin, stable candidate, release date when available, source, and errors. Claude Code uses only the native `stable` channel; lagged releases are unavailable. The `oc` candidate stays in the pinned minor stream and newer streams appear in the note. A candidate older than the pin is for information only; never downgrade automatically.

Show the report and ask which pins the user wants changed. Ask separately before moving `oc` to another minor stream. If a source or install asset cannot be verified, explain the failure and resolve it before suggesting that pin for an update. Update only selected ARGs; preserve installer commands, executable paths, and version checks. For OpenCode, confirm its native executable still matches the policy paths in [ADR 0011](../../../adrs/adr0011-pin-sandbox-cli-versions.md).

After edits, review the diff, build with `podman build -t exoshell-base sandboxes/exoshell-base`, then run the image with an overridden entrypoint and smoke-check each changed CLI's version. If Podman is unavailable in the sandbox, report the limitation and the checks completed.
