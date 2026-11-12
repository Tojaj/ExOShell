# Glossary

The terms below are the ones that are easy to confuse because they come in
pairs. Each links to the page that covers it in full.

## Hosts and containers

| Term | Meaning |
| --- | --- |
| **Gateway host** | The machine running the OpenShell gateway, where you run `openshell`, `./build.sh`, and the launcher. On a single-machine setup this is your own Linux box. |
| **Gateway** | The OpenShell service that creates and supervises sandboxes, resolves provider credentials, and inspects requests. Configured in `~/.config/openshell/gateway.toml`. |
| **Sandbox** | One disposable rootless-Podman container holding one agent session. OpenShell names it; the launcher deletes it on exit unless you pass `--keep`. See [sessions](guide/sessions.md). |
| **Launcher** | `./run-exoshell-agent.sh`, which resolves configuration, selects a policy and providers, and asks the gateway for a sandbox. See [launcher options](reference/launcher.md). |

## Projects and mounts

| Term | Meaning |
| --- | --- |
| **Project** | The host directory you pass to the launcher. It decides what the agent can see and change. |
| **Host share** | An optional larger host directory that is mounted instead of the project alone; the project must live inside it. Widens the writable mount to the whole tree. |
| **`/workspace`** | The mount point inside the sandbox. The project (or host share) appears here, and the agent starts in the project's location below it. |
| **`/sandbox`** | The sandbox user's home and agent runtime-state area. It is not where your sources live, and it is discarded with the sandbox. |

Covered in [projects and workspaces](guide/workspaces.md).

## Providers and credentials

| Term | Meaning |
| --- | --- |
| **Provider profile** | A reusable, credential-free definition of a service type: which credential variable it binds, which endpoints it permits, and which binaries may reach them. Imported once per machine; IDs start with `exoshell-`. |
| **Provider instance** | A named object holding your actual credential for one profile. This is what you attach with `--provider` and the TOML `providers` array. |
| **Credential** | The real secret. It is stored by OpenShell on the gateway host and never enters the sandbox. |
| **Placeholder** | What the agent sees in place of a credential. The gateway substitutes the real value only on requests the provider permits, so reading the environment inside the sandbox does not disclose the secret. |

Covered in [providers](integrations/index.md).

## Policies

| Term | Meaning |
| --- | --- |
| **Policy** | The YAML file selected at launch that constrains filesystem, process, and network access for the sandbox's whole lifetime. |
| **Portable baseline policy** | [`policies/policy.yaml`](https://github.com/Tojaj/ExOShell/blob/main/policies/policy.yaml), the policy shipped with this project. It audits general network traffic and relies on provider endpoints to enforce credential boundaries; it is not a blanket deny. |
| **Effective policy** | What the sandbox actually runs: the selected policy combined with the `_provider_*` entries contributed by every attached provider. |
| **Policy overlay** | A small `network_policies` fragment pushed to an *already running* sandbox to grant one extra capability, such as opening a pull request. Reverted with `--revert`, and gone when the sandbox is deleted. |
| **`enforce` vs `audit`** | `enforce` blocks requests outside the rule. `audit` **permits** what it records — useful while discovering endpoints, not a substitute for a scoped rule. |

Covered in [create a custom policy](customize/policies.md) and
[policy overlays](customize/overlays.md).
