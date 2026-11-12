# Inference providers

## Codex CLI

`exoshell-codex-cli` runs Codex with an OpenAI API key, rather than ChatGPT OAuth. It
allows unresolved provider placeholders in inference request bodies so a
credential from another provider is never substituted into a conversation sent
to OpenAI.

Do not attach it with `exoshell-opencode-openai`: both export `OPENAI_API_KEY`.

```bash
openshell provider profile lint -f provider-profiles/provider-codex-cli.yaml
openshell provider profile import -f provider-profiles/provider-codex-cli.yaml
```

```bash
openshell provider create --name exoshell-codex \
  --type exoshell-codex-cli --credential OPENAI_API_KEY
```

The custom profile supplies `OPENAI_API_KEY`; the built-in Codex profile uses
`CODEX_AUTH_*` authentication instead. OpenShell's native classifier forwards
valid conversation placeholders without resolving their secret values. Body
rewriting and `allow_uninspected_credentials` remain disabled. See
[ADR-0042](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0042-native-inference-body-classification.md).

Smoke test by launching Codex with the provider and asking it to complete a
small request:

```bash
./run-exoshell-agent.sh --policy policies/policy.yaml --agent codex --provider exoshell-codex . -- exec 'reply with OK'
```

## Claude Code CLI

`exoshell-claude-code-cli` supplies an Anthropic API key to Claude Code. Inference
request bodies can contain opaque placeholders from other providers, so the
native body classifier forwards valid placeholders unchanged. Only the
authentication header resolves the API key; inference body rewriting stays disabled.

Do not attach it with `exoshell-opencode-anthropic`: both export `ANTHROPIC_API_KEY`.
Subscription OAuth is not supported because it requires sandbox-readable
persistent credentials.

```bash
openshell provider profile lint -f provider-profiles/provider-claude-code-cli.yaml
openshell provider profile import -f provider-profiles/provider-claude-code-cli.yaml
```

```bash
openshell provider create --name exoshell-claude-code \
  --type exoshell-claude-code-cli --credential ANTHROPIC_API_KEY
```

The provider keeps the API key behind an OpenShell placeholder rather than
placing readable credentials in Claude Code state.

Smoke test:

```bash
./run-exoshell-agent.sh --policy policies/policy.yaml --agent claude --provider exoshell-claude-code . -- \
  -p 'reply with OK'
```

## OpenCode built-in inference

Models served through `opencode.ai`, including free models in OpenCode's model
picker, use the baseline policy's `opencode_site` endpoint rather than the
OpenAI, Anthropic, or OpenRouter profiles below. It uses OpenShell's native body
classifier, as do the inference provider profiles. Valid issued placeholders
and unknown literals pass as opaque text; invalid, revoked, or expired references
can be denied. Body credential rewriting stays disabled. See
[ADR-0042](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0042-native-inference-body-classification.md).

If OpenCode reports "A credential placeholder in the request body cannot be
forwarded", check that the CLI, gateway, and supervisor versions match and the
referenced provider is still valid. Recreate the session after provider changes
if it retains stale placeholders. Do not restore the broad scanning exception
or enable body credential rewriting to bypass the error.

To smoke-test, select an available model served by `opencode.ai`, send a prompt
containing a synthetic string such as `openshell:resolve:env:example_TOKEN`, and
send a follow-up. Both requests should reach inference without the body
credential denial. Never use a real credential for this test.

## OpenCode with OpenRouter

`exoshell-opencode-openrouter` supplies an OpenRouter API key to OpenCode. It is the
default OpenCode provider in the example launcher configuration.

Do not use OpenCode's `/connect` flow. It writes readable credentials to
`~/.local/share/opencode/auth.json`; OpenCode must consume the provider-exported
placeholder instead.

```bash
openshell provider profile lint -f provider-profiles/provider-opencode-openrouter.yaml
openshell provider profile import -f provider-profiles/provider-opencode-openrouter.yaml
```

```bash
openshell provider create --name exoshell-opencode-openrouter \
  --type exoshell-opencode-openrouter --credential OPENROUTER_API_KEY
```

The profile grants OpenCode access only to OpenRouter and retains opaque
placeholders in inference request bodies.

Smoke test by starting OpenCode with a known OpenRouter model:

```bash
./run-exoshell-agent.sh --policy policies/policy.yaml --agent opencode --provider exoshell-opencode-openrouter . -- \
  run --model openrouter/example 'reply with OK'
```

(The v2 TUI accepts no `--model` flag; use `run --model` for non-interactive
smoke tests. See [ADR-0040](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0040-opencode-v2-migration.md).)

## OpenCode with OpenAI

`exoshell-opencode-openai` supplies an OpenAI API key to OpenCode. Use it when OpenCode
should call OpenAI directly instead of OpenRouter.

Do not attach it with `exoshell-codex`: both export `OPENAI_API_KEY`. Do not use
OpenCode's `/connect` flow because it persists readable credentials.

```bash
openshell provider profile lint -f provider-profiles/provider-opencode-openai.yaml
openshell provider profile import -f provider-profiles/provider-opencode-openai.yaml
```

```bash
openshell provider create --name exoshell-opencode-openai \
  --type exoshell-opencode-openai --credential OPENAI_API_KEY
```

The profile keeps the key provider-backed while allowing OpenCode's inference
requests to carry opaque placeholders from other integrations.

Smoke test by launching OpenCode with this provider and selecting an OpenAI
model supported by the image configuration.

## OpenCode with Anthropic

`exoshell-opencode-anthropic` supplies an Anthropic API key to OpenCode. Use it when
OpenCode should call Anthropic directly.

Do not attach it with `exoshell-claude-code`: both export `ANTHROPIC_API_KEY`. Do not
use OpenCode's `/connect` flow because it persists readable credentials.

```bash
openshell provider profile lint -f provider-profiles/provider-opencode-anthropic.yaml
openshell provider profile import -f provider-profiles/provider-opencode-anthropic.yaml
```

```bash
openshell provider create --name exoshell-opencode-anthropic \
  --type exoshell-opencode-anthropic --credential ANTHROPIC_API_KEY
```

The profile uses the same placeholder-safe inference pattern as the other
OpenCode backends.

Smoke test by launching OpenCode with this provider and selecting an Anthropic
model supported by the image configuration.
