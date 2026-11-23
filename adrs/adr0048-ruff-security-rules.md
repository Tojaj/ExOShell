---
status: accepted
date: 2026-11-23
topics:
  - ci
  - security
---

# 48. Enable Ruff security rules

## Context

ExOShell already runs Ruff locally and in CI. The launcher and policy overlay
tool run commands and read configuration. In a trial run of Ruff's security
rules, most findings came from intentional subprocess calls and executable
lookup through `PATH`.

## Decision

We decided to enable Ruff's stable `S` rules in the existing Python lint
hook. We will allow assertions and routine subprocess calls in the relevant
test directories. We will use line-specific exceptions for reviewed patterns
in application code, including intentional subprocess calls, fixed sandbox
mount paths, and the policy overlay loader that subclasses `yaml.SafeLoader`
to reject duplicate keys.

## Consequences

Contributors get the same Python security checks locally and in CI, including
checks for `shell=True` and unsafe YAML loading. Reviewers will check the
reason for each new exception.

## References

- [ADR-0045: Unprivileged CI](adr0045-unprivileged-first-phase-ci.md)
- [Ruff configuration](../ruff.toml)
- [Ruff security rules](https://docs.astral.sh/ruff/rules/#flake8-bandit-s)
