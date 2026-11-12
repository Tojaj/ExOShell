# Sessions and credentials

OpenShell generates a unique sandbox name for each launcher invocation. Each
sandbox has `managed-by=exoshell`, `project=<normalized project basename>`,
and `agent=<selected agent>` labels. The runner passes `--no-keep`, so the
sandbox is deleted when the agent exits. For debugging, pass `--keep` to retain
the sandbox instead. With `--no-share`, the project label is `project=ephemeral`.

Discover launcher-created sandboxes with labels:

```bash
openshell sandbox list --selector managed-by=exoshell
openshell sandbox list --selector managed-by=exoshell,project=exoshell -o json
```

The default `sandbox list` table does not show labels; use a selector or JSON
or YAML output to inspect them.

## Credentials and state

API credentials remain provider-backed placeholders. Claude Code supports an
Anthropic API key here; subscription OAuth is out of scope because it needs
sandbox-readable persistent credentials. OpenCode can use the provided OpenAI,
Anthropic, or OpenRouter profiles.

!!! warning "Do not use OpenCode `/connect`"
    It writes readable credentials to
    `~/.local/share/opencode/auth.json`. The attached provider already supplies
    the key as a placeholder.

Agent state remains in the sandbox container layer. It is discarded with the
default `--no-keep` lifecycle, including histories, onboarding choices,
user-level model selections, and credentials written by interactive login
flows. A sandbox launched with `--keep` retains that state for debugging and
must be deleted after investigation. Project-owned `.claude/`, `.opencode/`,
and `opencode.json` files survive under `/workspace`.
