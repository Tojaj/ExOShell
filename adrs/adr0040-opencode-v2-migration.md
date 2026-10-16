---
status: accepted
date: 2026-10-16
author: Tomas Mlcoch
topics:
  - sandbox-image
  - launcher
  - agent-state
---

# 40. Migrate the Pinned OpenCode 1 Line to OpenCode 2

## Context

The image pinned OpenCode 1 (`opencode-ai@1.19.0`, npm). OpenCode 2 ships under
a new npm package (`@opencode/cli`, verified at `2.0.31`) with the same
`opencode` command, plus an `opencode2` alias for the same executable. Three
migration questions had to be answered empirically, because the v2 docs leave
runtime merge behavior partly implicit:

1. **Install layout.** The v2 postinstall hardlinks the platform package
   (`@opencode/cli-linux-<arch>/bin/opencode`) to
   `@opencode/cli/bin/opencode.exe`, so the Landlock `binaries:` allowlist
   moves from `/usr/lib/node_modules/opencode-ai/**` to
   `/usr/lib/node_modules/@opencode/**` (plus the exact exe path).
2. **CLI surface.** Verified against the 2.0.31 binary: the TUI accepts no
   `--model`/`--agent` flags, and `run` accepts `--model provider/model#variant`
   but no `--variant`. The old launcher injections (`--model` before `run`,
   `--variant` after `run`, `--model` for the TUI) all fail with
   `Unrecognized flag`. `mini` keeps `--model provider/model`/`--agent`.
3. **Config shape.** `autoupdate: bool` becomes `update: "disable"`, flat
   `mcp.<name>.enabled` becomes `mcp.servers.<name>.disabled` (inverted),
   `agent.{build,plan}` becomes `agents.{build,plan}`, and per-agent variants
   fuse into the model selector (`"provider/model#variant"` or the
   `{providerID, model, variant}` object); a sibling `variant` field is
   silently dropped. TUI settings move from `tui.json` to `cli.json`
   (`$schema: https://opencode.ai/v2/cli.json`) with namespaced keybind IDs.
   Higher-precedence layers replace whole MCP server objects, so a partial
   inline entry would discard the image definition. As a backstop, v2.0.31
   silently migrates the v1 keys in memory (verified), but we do not rely on
   undocumented migration.

A further v2 behavior constrains testing: CLI commands are served by a
per-user background server, so `debug`/`mcp list` can observe a stale
server's environment, a cold server can report no MCP servers, and
`service stop` returns before the port is released. Suite tests that need a
fresh server stop it and poll `service status` until `stopped`.

## Decision

We will pin `@opencode/cli@2.0.31` (npm, same overlay method as before) and
fully replace the v1 shapes with canonical v2 ones; no v1-key fallback stays.
The image uninstalls the `opencode-ai` package first: both packages provide
an `opencode` bin and npm aborts with EEXIST instead of overwriting another
package's file (skipped when no v1 package is installed):

- Image `opencode.json` uses `update: "disable"` and
  `mcp.servers.atlassian` (`disabled: true`); `tui.json` becomes `cli.json`
  with `terminal.suspend: none`, `prompt.stash: ctrl+s`,
  `prompt.stash.list: alt+s`.
- The startup helper writes `mcp.servers.atlassian.disabled` (installing the
  canonical full server definition when the inline layer has no typed one,
  preserving a complete custom one) and folds launcher model/effort into
  `agents.build`/`agents.plan` as `model` or `model#variant`.
- The launcher injects `--model <model[#variant]>` after the `run` token only,
  never for interactive sessions (those travel via `EXOSHELL_OPENCODE_DEFAULTS`,
  now also supporting model-only), and raises a guided error when effort meets
  a native `--model` (fusing would rewrite forwarded arguments) or a model
  that already carries `#variant`.
- Policy and provider-profile `binaries:` paths move to the `@opencode` tree;
  the version checker tracks `@opencode/cli` (linux x64/arm64 optionals, both
  `opencode`/`opencode2` bins mapping to `bin/opencode.exe`).
- The v2 background service stays enabled (no `--standalone`): agent state,
  including the server, lives in the container layer and is discarded with
  `--no-keep`, while `run --continue/--session` keeps working.

## Consequences

- `run --variant` and TUI `--model`/`--agent` invocations that worked under
  v1 now fail; effort-with-native-`--model` must be expressed as
  `--model provider/model#variant`. The launcher error says so.
- A project-level custom `atlassian` server object is superseded by the
  launcher-managed inline definition (credential governance wins, as under
  v1's "runtime overrides control the entry" rule); unrelated servers and
  custom fields of a complete inline definition are preserved.
- The installed-client runtime test needs a v2 binary (skips otherwise) and
  restarts the background service per iteration.
- Each future OpenCode bump remains a checkpoint that `/proc/<pid>/exe`
  still matches `binaries:`, per ADR-0011.

## References

- [`sandboxes/exoshell-base/Dockerfile`](../sandboxes/exoshell-base/Dockerfile)
- [`sandboxes/exoshell-base/opencode.json`](../sandboxes/exoshell-base/opencode.json)
- [`sandboxes/exoshell-base/cli.json`](../sandboxes/exoshell-base/cli.json)
- [`sandboxes/exoshell-base/exoshell-agent`](../sandboxes/exoshell-base/exoshell-agent)
- [OpenCode 2 docs](https://opencode.ai/v2/docs/) (config, agents, models,
  MCP servers, CLI settings, keybinds)
- [ADR-0011](adr0011-pin-sandbox-cli-versions.md) — pinned CLI versions
- [ADR-0036](adr0036-per-agent-model-and-effort-defaults.md) — model/effort
  defaults (v1 mechanism this supersedes for OpenCode)
