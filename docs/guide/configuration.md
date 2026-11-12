# Launcher configuration

A configuration file saves you from repeating `--policy`, `--provider`, and the
other options on every launch. This page covers which file the launcher reads
and what you can put in it.

## Where the launcher looks

The launcher loads exactly one configuration file, in this priority order:

1. Explicit `--config PATH` (any filename; relative paths use the caller's
   current directory and bypass discovery).
2. `.exoshell.local.toml` in the caller's current working directory.
3. `$XDG_CONFIG_HOME/exoshell/exoshell.local.toml`, defaulting to
   `~/.config/exoshell/exoshell.local.toml` when `XDG_CONFIG_HOME` is unset,
   empty, or relative.
4. `/etc/exoshell/exoshell.local.toml`.
5. Built-in defaults: the local image, Codex, provider `exoshell-codex`, and
   no optional integrations.

Two rules account for most surprises:

- **Files are not merged.** Only the selected file is loaded. A missing key
  falls back to the built-in default, even when a lower-priority file supplies
  a value for it.
- **Discovery starts where you are, not where the launcher is.** It looks in
  the caller's current directory, never beside the launcher, inside the
  positional project, or in parent directories. (It also ignores uppercase
  filename aliases and `XDG_CONFIG_DIRS`.)

Copy `.exoshell.local.toml.example` to `.exoshell.local.toml` in a working
directory for local defaults, or to the user configuration path for defaults
across projects. A checkout config is therefore discoverable only when you run
from that checkout; to call the launcher from elsewhere, pass
`--config /path/to/checkout/.exoshell.local.toml` or move the file to the user
configuration path, adjusting its relative paths.

CLI options override the selected file. TOML paths resolve relative to the file
itself; CLI paths resolve relative to the caller's directory. Absent discovery
candidates are skipped, but an invalid, unreadable, or non-file candidate stops
the launch, as does a missing explicit `--config` file.

## Choose a policy

Select a policy with `--policy /path/to/policy.yaml` or the TOML `policy`
setting. The launcher stops before provisioning if no policy is selected or
the selected path does not exist or is not a regular file. For the portable
baseline, pass the path to
[`policies/policy.yaml`](https://github.com/Tojaj/ExOShell/blob/main/policies/policy.yaml) in your ExOShell checkout.

Explicit `--no-policy` clears any configured policy and lets OpenShell select
one. This can select an environment or inherited image policy, including the
community base image's policy. OpenShell's restrictive default applies only
when no other policy source exists; see its
[default-policy documentation](https://docs.nvidia.com/openshell/how-it-works/policies/default-policy)
and [ADR-0035](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0035-explicit-launcher-policy-selection.md).

The launcher records the selected policy path in the sandbox annotation
`exoshell.policy-source-file`. A [policy overlay](../customize/overlays.md)
reverts to that recorded source unless `--base-file` overrides it. Sandboxes
without the annotation, including `--no-policy` launches, require
`--base-file`; the overlay helper does not guess from launcher configuration.

## Compose providers

Providers in the common `providers` array are attached to every agent;
providers under `[agents.<agent>]` are added for that agent only:

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

CLI `--provider` options replace that composed list rather than adding to it,
so a launch that passes any `--provider` must name every instance it needs,
including the inference provider. `--no-providers` attaches none.

## Debug the selection

Pass `-v` or `--verbose`:

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
