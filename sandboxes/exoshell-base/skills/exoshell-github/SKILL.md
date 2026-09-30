---
name: exoshell-github
description: >
  ExOShell-specific GitHub guidance. Read this in addition to the inherited
  github skill whenever a GitHub task runs in an ExOShell sandbox, especially
  for GraphQL, host selection, or policy denials.
---

# ExOShell GitHub

Read the inherited `github` skill for GitHub CLI usage. This skill supersedes
its blanket GraphQL restriction when running in an ExOShell sandbox.

## Authentication and hosts

- The launcher-selected `GH_HOST` identifies the GitHub host. Provider profiles
  supply credentials and enforce their endpoint access; host selection does not
  create a provider or grant access.
- Do not mount host GitHub configuration or persist credentials in the sandbox.
- Use the selected host's provider and policy. A host-specific provider profile
  and policy entry are required for each additional GitHub host.

## GraphQL policy

- ExOShell's baseline policy permits GraphQL queries at
  `https://api.github.com/graphql`. Therefore `gh` commands that use GraphQL
  can work when the applicable GitHub provider is attached.
- GraphQL mutations require an active policy overlay that explicitly grants
  the required operation and fields. Do not work around a denial by bypassing
  the proxy or using a different credential path.
- There must be exactly one `api.github.com/graphql` endpoint in the effective
  policy. Adding another endpoint narrows permissions through intersection; it
  cannot grant a mutation denied by the original endpoint.
- If a necessary request is denied, follow the installed OpenShell policy
  guidance and request the narrowest policy change.
