---
status: accepted
date: 2026-10-22
topics:
  - providers
  - credentials
  - policy
---

# 42. Use native classification for inference body placeholders

## Context

[ADR-0008](adr0008-custom-codex-provider-allow-uninspected-credentials.md)
and [ADR-0041](adr0041-opencode-site-opaque-conversation-placeholders.md)
disabled body scanning to prevent conversation history from blocking inference.
The exception also bypasses checks on invalid or unavailable references.

OpenShell PR #3246 fixed the underlying classifier and is already an ancestor
of v0.1.2. The v0.1.5 source and tests confirm that unknown literals and valid
issued placeholders, including the model provider's own placeholder, are
forwarded unchanged when body rewriting is disabled. Authentication headers
resolve independently. Invalid or unavailable references remain subject to
denial. Retaining the exception would bypass those native checks unnecessarily.

## Decision

We will require OpenShell v0.1.5 or newer and remove
`allow_uninspected_credentials` from inference profiles and the baseline
`opencode.ai` endpoint. We will keep inference body rewriting disabled and
retain custom profile identities, API-key authentication, endpoint permissions,
and binary selectors. GWS's intentional token-body rewriting will remain.

## Consequences

- Conversation replay uses upstream classification without secret substitution.
- Operators must update imported profiles and selected custom policies; file
  edits alone do not update gateway resources.
- Expired, revoked, or malformed placeholders can still cause failures. Repair
  provider state or recreate a stale session rather than bypassing scanning.
- Agent smoke checks remain necessary because upstream regression tests use
  controlled destinations rather than live model services.

## References

- [OpenShell PR #3246](https://github.com/NVIDIA/OpenShell/pull/3246)
- [Fix ancestry in v0.1.2](https://github.com/NVIDIA/OpenShell/compare/226a83b3232ddf3e6534e4c0889c5a1c04b22297...v0.1.2)
- [v0.1.5 body classifier and regression tests](https://github.com/NVIDIA/OpenShell/blob/v0.1.5/crates/openshell-core/src/secrets_body.rs)
