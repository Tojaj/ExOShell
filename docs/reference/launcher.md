# Launcher options

```text
./run-exoshell-agent.sh [options] [project] [-- agent-arguments...]
```

`project` is an existing host directory, defaulting to the caller's current
directory. Options after `--` belong to the agent. For the installed launcher's
complete help, run `./run-exoshell-agent.sh --help`.

| Option | TOML key | Meaning |
| --- | --- | --- |
| `--agent codex\|claude\|opencode` | `agent` | Select the agent; default `codex` |
| `--config PATH` | — | Load exactly this configuration file |
| `-v`, `--verbose` | — | Report configuration selection and effective settings |
| `--image IMAGE` | `image` | Select the OCI image; default `localhost/exoshell-local:latest` |
| `--policy PATH` / `--no-policy` | `policy` | Select a policy, or delegate selection to OpenShell (which may then apply an environment or inherited image policy — see [configuration](../guide/configuration.md#choose-a-policy)) |
| `--provider NAME` / `--no-providers` | `providers`, `agents.<agent>.providers` | Repeat to replace the composed provider list, or clear it |
| `--host-share PATH` | `host_share` | Mount a source tree containing the selected project |
| `--no-share` | — | Suppress project and kubeconfig mounts; use a disposable workspace |
| `--skill PATH` / `--no-skills` | `skills` | Repeat to replace skill sources, or disable imports |
| `--model VALUE` / `--no-model` | `agents.<agent>.model` | Override or suppress the starting model setting |
| `--effort VALUE` / `--no-effort` | `agents.<agent>.effort` | Override or suppress the starting effort setting |
| `--kubeconfig PATH` / `--no-kubeconfig` | `kubeconfig` | Mount a kubeconfig read-only, or disable the mount |
| `--github-host HOST` / `--no-github-host` | `github_host` | Select or clear the GitHub CLI/Git host |
| `--gitlab-host HOST` / `--no-gitlab-host` | `gitlab_host` | Select or clear the GitLab CLI/Git host |
| `--keep` | — | Retain the sandbox after exit for debugging |
| `-h`, `--help` | — | Show help |

CLI paths resolve from the caller's directory; TOML paths resolve from the
selected configuration file. CLI options override file settings. Native agent
model/effort arguments take precedence over ExOShell's starting values.

See [configuration](../guide/configuration.md) for discovery and provider
composition, [workspaces](../guide/workspaces.md) for mount behavior, and the
[example TOML](https://github.com/Tojaj/ExOShell/blob/main/.exoshell.local.toml.example)
for available settings. The example includes optional integrations: adapt it to
the providers and paths you actually have.
