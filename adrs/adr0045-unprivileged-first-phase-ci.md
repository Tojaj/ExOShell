---
status: accepted
date: 2026-11-12
topics:
  - ci
  - security
---

# 45. Start CI with unprivileged file checks and unit tests

## Context

The project has unit tests and configuration files but no shared local checks
or required hosted result. Pull requests execute contributor-controlled code.
Combining validation and publication would expose credentials and persistent
state to that code before publication isolation has been designed.

## Decision

We will run the same pinned pre-commit configuration locally and in a GitHub
Actions job, alongside a separate Python 3.11 unit-test job. An aggregate `CI`
check will run after both jobs even on failure and require both to succeed.
Every PR targeting `main` and push to `main` will receive this result without
path filters; manual dispatch will also be available.

We will use fresh `ubuntu-24.04` hosted runners, 15-minute job limits, and
cancel superseded runs within the same event/ref. Token permissions will
default to none, with `contents: read` only for jobs that check out source.
Checkout will not persist credentials. Actions and hook repositories will use
verified immutable commit pins; tool dependencies will use exact versions.

We will use ordinary `pull_request` events, static shell commands, quoted
environment values, and fixed printf formats. We will exclude privileged
triggers (`pull_request_target`, `workflow_run`, and comments), secrets, write
permissions, self-hosted runners, caches, artifact handoffs, and publication.
Zizmor will run offline with its auditor persona and fail on findings without
SARIF upload permissions. This includes broad permissions that the default
persona may suppress for PR events whose token is normally restricted.

We will inspect unittest results and reject unexpected skips. Only the five
installed-client tests listed in the runner may skip on hosts, and only for
their specific missing-client reasons. A strict invocation will require zero
skips. Empty suites will fail as well.

We will run Gitleaks with redacted output on staged changes locally and on the
whole fresh checkout in CI; the staged-only upstream entry is insufficient for
hosted runs. Skillsaw will reject errors in agent instructions and skills while
leaving prose warnings advisory. Its custom rules, installed rule plugins, and
baseline suppression will be disabled when checking contributor-controlled
content. Both tools will use their upstream hooks with immutable commit pins.

## Consequences

- Contributors get automatic formatting and validation with the same tools
  used in CI, including the extensionless Python image helper and TOML example.
- The hosted jobs validate source without granting publication access.
- Initial formatting changes touch existing code without changing behavior.
- Cold tool installation costs time; there are no cross-run caches to trust.
- Repository administrators must enable `CI` as a required check after hosted
  rollout verification. The workflow alone cannot enforce branch protection.
- Container validation, publication, and Pages need separate designs. Host
  checks do not validate the built image or installed agents.

## References

- [Workflow](../.github/workflows/ci.yaml)
- [GitHub secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use)
- [Preventing pwn requests](https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/)
- [Untrusted input](https://securitylab.github.com/resources/github-actions-untrusted-input/)
- [Trusting building blocks](https://securitylab.github.com/resources/github-actions-building-blocks/)
- [New vulnerability patterns](https://securitylab.github.com/resources/github-actions-new-patterns-and-mitigations/)
- [Pre-commit](https://pre-commit.com/)
- [Zizmor operating modes](https://docs.zizmor.sh/usage/#operating-modes)
