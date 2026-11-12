# Launcher configuration

Arguments after `--` are passed unchanged to the selected executable. The
launcher loads one configuration file in this priority order:

1. Explicit `--config PATH` (any filename; relative paths use the caller's
   current directory and bypass discovery).
2. `.exoshell.local.toml` in the caller's current working directory.
3. `$XDG_CONFIG_HOME/exoshell/exoshell.local.toml`, defaulting to
   `~/.config/exoshell/exoshell.local.toml` when `XDG_CONFIG_HOME` is unset,
   empty, or relative.
4. `/etc/exoshell/exoshell.local.toml`.
5. Built-in defaults: the local image, Codex, provider `exoshell-codex`, and
   no optional integrations.

Absent discovery candidates are skipped. Invalid, unreadable, or non-file
candidates stop the launch; a missing explicit file is also an error. Only
the selected file is loaded: missing keys use built-in defaults, even if a
lower-priority file supplies them. CLI options override the selected file.
TOML paths resolve relative to that file; CLI paths use the caller's directory.
Discovery does not search the positional project, parent directories, or
the launcher's directory, and does not use uppercase aliases or `XDG_CONFIG_DIRS`.

Copy `.exoshell.local.toml.example` to `.exoshell.local.toml` in a working
directory for local defaults, or to the user configuration path for defaults
across projects. A checkout config remains discoverable when running from
that checkout. If you previously relied on lookup beside the launcher while
calling it elsewhere, pass `--config /path/to/checkout/.exoshell.local.toml`
or move the config to the user directory. Adjust relative TOML paths when
moving the file.

The launcher records the selected policy path in the sandbox annotation
`exoshell.policy-source-file`. Overlay `--revert` uses this source unless
`--base-file` overrides it. Sandboxes without that annotation require
`--base-file`; the helper does not guess from launcher configuration.

For configuration debugging, pass `-v` or `--verbose`:

```bash
./run-exoshell-agent.sh --verbose /path/to/project
```

The runner reports the absolute selected config path, or that built-in defaults
are in use, followed by the effective launcher settings on stderr. These values
include CLI overrides, the composed provider list, and resolved host and
container paths. Unset values appear as `null`. The config path is reported
before loading the file; effective settings appear after successful validation
and before image checks and sandbox creation. Verbosity is a launcher option;
flags after `--` are passed to the agent.

Common providers compose with providers for the selected agent:

```toml
agent = "codex"
providers = ["exoshell-github", "exoshell-gws"]

[agents.codex]
providers = ["exoshell-codex", "exoshell-atlassian-mcp"]

[agents.claude]
providers = ["exoshell-claude-code", "exoshell-atlassian-mcp"]

[agents.opencode]
providers = ["exoshell-opencode-openrouter", "exoshell-atlassian-mcp"]
```

Select a policy with `--policy /path/to/policy.yaml` or the TOML `policy`
setting. The launcher stops before provisioning if no policy is selected or
the selected path does not exist or is not a regular file. CLI paths resolve
relative to the caller's directory; TOML paths resolve relative to the selected
configuration file. For the portable baseline, pass the path to
[`policies/policy.yaml`](https://github.com/Tojaj/ExOShell/blob/main/policies/policy.yaml) in your ExOShell checkout.

Explicit `--no-policy` clears any configured policy and lets OpenShell select
one. This can select an environment or inherited image policy, including the
community base image's policy. OpenShell's restrictive default applies only
when no other policy source exists; see its
[default-policy documentation](https://docs.nvidia.com/openshell/how-it-works/policies/default-policy)
and [ADR-0035](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0035-explicit-launcher-policy-selection.md).
