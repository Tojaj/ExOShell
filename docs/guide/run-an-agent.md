# Run an agent

After [setup](../get-started.md), use the launcher from the ExOShell checkout.
These examples assume a selected policy and the appropriate provider instances
in your [configuration](configuration.md).

```bash
./run-exoshell-agent.sh /path/to/project
./run-exoshell-agent.sh --agent claude /path/to/project
./run-exoshell-agent.sh --agent opencode /path/to/project
```

Codex is the default. The project defaults to the caller's current directory.
Each launch creates a separate sandbox; leaving the agent deletes it by default.

## Pass agent arguments

Options before `--` belong to ExOShell; everything after it goes unchanged to
the selected agent:

```bash
./run-exoshell-agent.sh --agent codex /path/to/project -- exec 'Explain this project'
./run-exoshell-agent.sh --agent claude /path/to/project -- -p 'Explain this project'
```

Use ExOShell's `--model` and `--effort` options for starting selections, including
OpenCode's interactive TUI. Supported values depend on the agent and backend.
See [models and effort](models.md).

## Choose what to share

By default, only the selected project is mounted at `/workspace`. Use
`--host-share` for a larger source tree, or `--no-share` for a disposable
workspace. See [projects and workspaces](workspaces.md).

Git commits use the selected project's effective host Git name and email when
available. Configure these on the host for the project before launching.
Forge host selection and provider credentials are separate; see
[GitHub and GitLab](../integrations/forges.md).

## Diagnose a launch

```bash
./run-exoshell-agent.sh --verbose /path/to/project
```

Verbose output shows the selected config, effective settings, and resolved
paths. Use `--keep` to retain the sandbox after exit for investigation, then
delete it when finished. See [sessions](sessions.md) and
[troubleshooting](../reference/troubleshooting.md).
