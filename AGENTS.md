# ExOShell

ExOShell provides reusable NVIDIA OpenShell provider profiles, sandbox policies,
images, and a launcher for coding agents. Read SPEC.md for the implemented
behavior and CUSTOMIZATION.md for extension points.

## Environment and discovery

Check `whoami` when determining whether this session runs as `sandbox` inside
OpenShell. Container builds may require the gateway host.

Use upstream documentation and source to verify OpenShell behavior:

- https://docs.nvidia.com/openshell/sandboxes/providers-v2
- https://docs.nvidia.com/openshell/reference/sandbox-compute-drivers
- https://docs.nvidia.com/openshell/reference/policy-schema
- https://github.com/NVIDIA/OpenShell
- https://github.com/NVIDIA/OpenShell-Community

Load `./AGENTS.local.md` if available for local specific guidance.

## Design and publication

- Keep shared configuration portable. Put organization-specific hostnames,
  provider profiles, policies, images, and model choices in a separate
  customization repository or ignored machine-local configuration.
- Use reserved example domains in public documentation. Never commit credentials,
  authenticated CLI state, private infrastructure inventories, or diagnostics.
- Prefer OpenShell capabilities and image configuration to complex wrappers.
  Consult the user about major launcher or architecture changes.
- Record major design decisions in brief ADRs. Read adrs/AGENTS.md and reference
  upstream documentation or source so decisions can be revisited as it evolves.
- Preserve license and copyright attribution.

## AI attribution

Include `Assisted-by: AGENT_NAME:MODEL_VERSION` in commit messages and pull
request descriptions, using the actual tool and model version.

## Contributing

Read CONTRIBUTING.md when you are about to contribute (commit, etc.).
