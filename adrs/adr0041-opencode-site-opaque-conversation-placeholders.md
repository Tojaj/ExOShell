---
status: superseded
superseded-by: adr0042-native-inference-body-classification.md
date: 2026-10-16
topics:
  - opencode
  - credentials
  - policy
---

# 41. Forward opaque conversation placeholders to OpenCode's inference host

Superseded by [the native OpenShell decision](adr0042-native-inference-body-classification.md).

## Context

[ADR-0008](adr0008-custom-codex-provider-allow-uninspected-credentials.md)
permits opaque credential placeholders in Codex conversation bodies without
resolving them. The OpenCode OpenAI, Anthropic, and OpenRouter profiles already
apply the same exception to their inference endpoints.

OpenCode also offers models through `opencode.ai`, including the free model
reported in issue #4. That host is admitted by the baseline `opencode_site`
entry, not one of those provider profiles. Its default body scanning rejects
conversation history containing placeholder syntax, even with audit enforcement.
Once a placeholder enters history, subsequent model requests fail as well.

Removing placeholders from every tool result or conversation is fragile.
Enabling `request_body_credential_rewrite` instead would request secret
substitution in conversation bodies, which is not the intended behavior.

## Decision

We will set `allow_uninspected_credentials: true` on the baseline
`opencode.ai:443` REST endpoint and leave `request_body_credential_rewrite`
disabled. We will preserve its existing access, enforcement, and OpenCode-only
binary selectors. The model catalog and other baseline hosts will retain body
scanning.

## Consequences

- OpenCode inference requests can carry opaque placeholders from tool output
  without resolving the underlying credentials into conversation bodies.
- The exception disables placeholder body scanning for all requests matched by
  this endpoint, including account requests; it is not limited to foreign
  placeholders or one model. It does not make actual secrets in prompts safe.
- Custom policies copied from older baselines need the same endpoint change.
  No provider update or image rebuild is required when selecting the updated
  policy at launch. Running sandboxes need a network policy update or recreation.
- A future binding-aware upstream fix may allow removal of this workaround.

## References

- [ExOShell issue #4](https://github.com/Tojaj/ExOShell/issues/4)
- [Baseline policy](../policies/policy.yaml)
- [OpenShell endpoint schema](https://github.com/NVIDIA/OpenShell/blob/main/crates/openshell-policy-schema/src/lib.rs)
- [OpenShell policy reference](https://docs.nvidia.com/openshell/reference/policy-schema)
- [Upstream placeholder body-scan issue](https://github.com/NVIDIA/OpenShell/issues/3237)
