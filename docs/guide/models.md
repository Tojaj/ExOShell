# Starting model and effort

Set optional `model` and `effort` strings in each `[agents.codex]`,
`[agents.claude]`, or `[agents.opencode]` section. Only the selected agent's
values apply. Omitting either setting preserves that agent's native defaults,
including defaults supplied by your image. Model IDs and supported effort
levels depend on the agent, model, and provider; ExOShell does not maintain a
model catalog or translate effort levels into a universal scale.

```toml
[agents.codex]
# model = "example-model"
# effort = "high" # Codex: model_reasoning_effort

[agents.claude]
# model = "sonnet"
# effort = "high" # Claude Code: --effort

[agents.opencode]
# model = "openrouter/example-model"
# effort = "high" # OpenCode: model variant (provider/model#variant); requires model
```

Override a configured value for one launch with `--model VALUE` or
`--effort VALUE` before the launcher separator. `--no-model` and `--no-effort`
ignore the corresponding ExOShell setting for that launch; they do not clear
the agent's own image, project, or user configuration. Omitting a launcher
option uses the configured value. For example:

```bash
./run-exoshell-agent.sh --effort low /path/to/project
./run-exoshell-agent.sh --no-model --no-effort /path/to/project
```

Explicit native options forwarded after `--` take precedence over ExOShell's
starting values. Codex accepts repeatable `-c`/`--config` overrides for
`model` and `model_reasoning_effort`; native `-m`/`--model` also overrides the
model. Claude accepts native `--model` and `--effort`. OpenCode accepts native
`-m`/`--model` for `run` and `mini` (the full-screen TUI accepts neither; use
ExOShell model/effort settings for it). Values after a native literal `--`
remain positional arguments. Verbose output reports ExOShell's selected
values, not native overrides or the agent's eventual model selection.

OpenCode effort requires an explicit model from the config or launcher option
(native `--model` cannot combine with a configured effort for `run`; express
the variant natively as `--model provider/model#variant`). Interactive launches
merge the model (with `#variant` when effort is set) into the built-in `build`
and `plan` agents through disposable `OPENCODE_CONFIG_CONTENT`, preserving
unrelated configuration and MCP settings. Custom OpenCode agents keep their own
model configuration. `opencode run` receives `--model` after the subcommand
instead. Users can change models and effort during the session.

Rebuild the base image and dependent images before using interactive OpenCode
model/effort: its startup helper consumes the launcher's model/variant pair.
Codex, Claude, and OpenCode `run` selections use native startup options.
See [ADR-0036](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0036-per-agent-model-and-effort-defaults.md) and
[ADR-0040](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0040-opencode-v2-migration.md).
