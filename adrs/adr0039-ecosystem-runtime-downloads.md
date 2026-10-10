---
status: accepted
date: 2026-10-10
topics:
  - providers
  - network-policy
---

# 39. Include runtime bootstrap access in ecosystem providers

## Context

[ADR-0024](adr0024-opt-in-package-registry-providers.md) made public package
registries independently selectable. pre-commit can also install isolated
language runtimes before downloading hook dependencies. Its Python process
queries `go.dev` and downloads Go from `dl.google.com`; nodeenv downloads Node
from `nodejs.org`. The existing npm and Go profiles omitted those destinations
and pre-commit's downloaded executables.

A development-policy grant would make runtime access implicit. A separate
runtime provider would preserve registry-only selection but add another
attachment for each ecosystem's hook setup. Extending the ecosystem profiles
keeps the existing selection mechanism while broadening their stated purpose.

## Decision

We will include official runtime bootstrap access in the existing opt-in npm
and Go profiles, retaining their IDs. Runtime endpoints will enforce read-only
HTTPS inspection and select `/download/release/**` on `nodejs.org`, `/dl/**`
on `go.dev`, and `/go/**` on `dl.google.com`.

We will include the Python interpreter patterns already supported by the PyPI
profile and the corresponding downloaded executables in pre-commit's default
cache. Existing package rules and agent binaries will remain available.

## Consequences

- Selecting an ecosystem also permits its official runtime downloads. Existing
  instances receive this additional access when their profile is updated.
- The `dl.google.com` path selector takes precedence over the baseline's
  Google audit wildcard without introducing an equal-specificity conflict.
- Custom cache locations, runtime mirrors and unofficial builds require adapted
  profiles. Network grants do not provide filesystem write permissions.
- Go module redirects and direct VCS fallbacks remain separate concerns; this
  change addresses the observed runtime setup denials.

## References

- [pre-commit Go installer](https://raw.githubusercontent.com/pre-commit/pre-commit/main/pre_commit/languages/golang.py)
- [nodeenv installer](https://raw.githubusercontent.com/ekalinin/nodeenv/master/nodeenv.py)
- [OpenShell policy schema and binary matching](https://docs.nvidia.com/openshell/how-it-works/policies/schema)
- [OpenShell policy update source](https://github.com/NVIDIA/OpenShell/blob/main/crates/openshell-cli/src/policy_update.rs)
- [Provider setup and updates](../providers.md#pre-commit-runtime-setup)
