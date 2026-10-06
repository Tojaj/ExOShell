---
status: accepted
date: 2026-10-06
topics:
  - codex
  - providers
  - agent-state
---

# 33. Initialize Codex login from the attached provider

## Context

Fresh disposable sandboxes have no cached Codex login. Codex 0.160.0 presents
interactive sign-in screens even with the provider-injected `OPENAI_API_KEY`
available. OpenShell exposes a credential reference in that environment
variable and resolves it at authorized outbound endpoints. An arbitrary dummy
key baked into an image is not that registered reference.

The existing image startup helper already prepares provider-backed integrations.
Codex supports reading an API key from stdin with `login --with-api-key`, avoiding
dependence on a hand-maintained authentication JSON schema.

## Decision

We will run the selected Codex executable with `login --with-api-key` before
starting the requested command whenever `OPENAI_API_KEY` is non-empty. We will
supply the current environment value through stdin and refresh the saved login
on each helper invocation. The image will default to file-based credential
storage. We will capture login output and stop on failure with a generic error.

We will keep initialization in the existing helper. Bare Codex commands can
reuse saved authentication, but will not acquire a new wrapper. Without a key,
the helper will leave authentication to Codex.

## Consequences

- Normal provider-backed launches skip interactive authentication screens.
- Images contain initialization logic and non-secret defaults; runtime login
  state contains the attached provider placeholder.
- Login state follows the sandbox lifecycle, including retention with `--keep`.
  Each helper invocation replaces previously cached authentication with the
  current attached credential.
- Higher-precedence Codex configuration can override the image's storage default.
- Base and derived images require rebuilding to adopt the change.
- An isolated probe with Codex 0.160.0 confirmed offline API-key login, `apikey`
  authentication mode, a `0600` auth file, and successful `login status`.

## References

- [Image startup helper](../sandboxes/exoshell-base/exoshell-agent)
- [Sandbox lifecycle for agent state](adr0019-sandbox-lifecycle-for-agent-state.md)
- [Codex login command](https://learn.chatgpt.com/docs/developer-commands?surface=cli#codex-login)
- [Codex credential storage](https://learn.chatgpt.com/docs/auth#credential-storage)
- [OpenShell provider profiles](https://docs.nvidia.com/openshell/how-it-works/providers/profiles)
