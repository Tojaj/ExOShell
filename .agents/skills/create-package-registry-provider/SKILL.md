---
name: create-package-registry-provider
description: Create or adapt an opt-in package registry provider profile for ExOShell. Use when adding a public or private package ecosystem, registry, or mirror; not for merely attaching an existing provider.
---

# Create a package registry provider

Follow [ADR 24](../../../adrs/adr0024-opt-in-package-registry-providers.md) and compare existing profiles in `provider-profiles/`. Keep access opt-in. Determine whether the profile belongs in public ExOShell or is local/internal.

1. Verify metadata, token, download, and redirect hosts and required HTTP methods from authoritative sources or observed requests. Use exact hosts and read methods. Scope any necessary POST to specific read-related paths; avoid publishing grants. Private registries also need suitable credentials and client configuration.
2. Include the resolved executables of the package manager and **all supported agents** (currently Codex, Claude Code, OpenCode), unless told otherwise. Check native and installed paths against existing profiles and policies; include interpreters and helpers that make requests. OpenShell matches the executable, not `argv`.
3. Evaluate `allow_encoded_slash: true` for `%2F` in request **paths**; `%2F` in a query alone does not need it. Check overlaps with baseline policies and attached providers, especially audit/enforce and path specificity. Cover redirect hosts for the same binaries.
4. If intended for public ExOShell, update `providers.md` and `.exoshell.local.toml.example`. Keep internal details out of shared files. Leave local config alone unless asked.
5. Parse YAML and run `openshell provider profile lint` when available. If possible, inspect the effective policy and try a read request. Report unavailable checks.

Print commands using the actual filename, ID, and instance name for `openshell provider profile lint -f ...`, `openshell provider profile import -f ...`, and `openshell provider create --name ... --type ...`. Explain how to attach the instance alongside the agent's inference provider.
