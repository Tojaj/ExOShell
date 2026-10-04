---
status: accepted
date: 2026-10-04
topics:
  - providers
  - naming
  - lifecycle
---

# 31. Namespace supplied provider identities and mark registry roles

## Context

ExOShell's profiles previously used unprefixed IDs such as `codex-cli` and
`npm-registry`, with unrelated instance names in examples and launcher defaults.
OpenShell catalogs can contain definitions from multiple sources. Metadata alone
can identify a source when inspecting a definition but is less visible in lists,
commands, and configuration. A prefix alone is visible but cannot express the
difference between a definition's origin and ownership of a created object.

Registry profiles currently grant consumption, including narrowly scoped npm
audit requests. Future publishing profiles need an explicit role distinction.
Only the maintainer uses ExOShell at this point, so active documentation can
describe the resulting setup directly without preserving previous examples.

## Decision

We will prefix all supplied profile IDs and suggested instance names with
`exoshell-`, prefix display names with "ExOShell", and annotate each definition
with `exoshell-origin: ExOShell`. Suggested instance names will drop a trailing
`-cli`; other names will match their profile IDs. Google Workspace's profile
will be `exoshell-gws-cli`, with instance `exoshell-gws` and filename
`provider-gws-cli.yaml`. Other profile filenames will remain stable.

We will suffix registry IDs and suggested instances with `-ro`, meaning
consumption without publishing. This includes npm audit and can include private
authenticated downloads. We will reserve `-publish` for future publishing
profiles and implement none now. Endpoint, binary, discovery, and credential
behavior will remain unchanged.

We will make the Codex launcher fallback `exoshell-codex` and the Atlassian
helper default and creation type `exoshell-atlassian-mcp`. Explicit instance
overrides and the Claude/OpenCode fallback behavior will remain supported.
Existing keyed Atlassian state will retain its keys; unkeyed state will migrate
under `atlassian-mcp`, independent of the new default.

We will treat the origin annotation as definition provenance, not installer
ownership. Future installers will record the objects they actually create.
Uninstall will consult that record and check modifications and dependencies;
neither prefix nor origin alone will authorize deletion.

## Consequences

- Supplied definitions are recognizable in catalogs and command examples.
- Renaming repository definitions does not rename gateway objects. Migration
  requires importing the new profiles, creating instances with credentials
  obtained through discovery or explicit input, updating local configuration,
  and starting fresh sandboxes before removing obsolete objects.
- The Atlassian replacement requires separate authorization. Existing access
  can still be refreshed with `sync --provider atlassian-mcp`; its host state
  must remain until replacement access is verified.
- Custom definitions and machine-local configuration require their owner's
  review. This change includes no installer, automatic migration, or publishing
  profiles and does not modify live gateways or downstream repositories.
- Historical ADRs retain their names and examples; active documentation uses
  the resulting naming scheme. Personal migration commands live separately.

## References

- [OpenShell provider profiles](https://docs.nvidia.com/openshell/how-it-works/providers/profiles)
- [OpenShell profile representation and annotations](https://github.com/NVIDIA/OpenShell/blob/main/crates/openshell-providers/src/profiles.rs)
- [Provider guide](../providers.md)
- [ADR-0024](adr0024-opt-in-package-registry-providers.md)
- [ADR-0027](adr0027-separate-customization-repository.md)
