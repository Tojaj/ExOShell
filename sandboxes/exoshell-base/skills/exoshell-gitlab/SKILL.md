---
name: exoshell-gitlab
description: >
  ExOShell-specific GitLab guidance. Read this in addition to the glab skill
  whenever a GitLab task runs in an ExOShell sandbox, especially when choosing
  a host, authenticating, using GraphQL, or resolving a policy denial.
---

# ExOShell GitLab

Read the `glab` skill for GitLab CLI usage. This skill describes the additional
constraints imposed by ExOShell's image, provider, and policy configuration.

## Authentication and hosts

- Do not run `glab auth login`, do not mount a host `glab` configuration, and
  do not write credentials into the sandbox. The selected OpenShell provider
  supplies `GITLAB_TOKEN` and `GLAB_TOKEN` only on authorized requests.
- Use the launcher-selected `GITLAB_HOST`. For a command targeting another
  configured host, pass `--hostname <host>` explicitly.
- Do not use `glab auth status --all`: it probes every registered host, which
  can include one without a provider credential. Use `glab auth status` or
  `glab auth status --hostname "$GITLAB_HOST"` instead.
- One sandbox can attach at most one GitLab provider because provider profiles
  export the same `GITLAB_TOKEN` and `GLAB_TOKEN` variable names.
- The image's `/etc/glab-cli/config.yml` contains host metadata only. It is
  deliberately not writable; credentials must remain provider-supplied.

## Policy behavior

- GitLab REST reads and Git clone/fetch work at the baseline provider policy.
  A command being valid `glab` syntax does not imply its network request is
  authorized by the active sandbox policy.
- `glab issue` and `glab mr` use REST. `glab api graphql` and `glab workitems`
  use `/api/graphql`.
- Each GitLab host has exactly one `/api/graphql` policy endpoint. Its baseline
  permits GraphQL queries only. Mutations require the active policy to grant
  them; do not add a second endpoint in an attempt to widen access because
  matching GraphQL endpoints intersect their permissions.
- If a necessary request is denied, follow the installed OpenShell policy
  guidance instead of trying to bypass the proxy or changing client-side
  authentication.

## API paths

GitLab project API paths encode namespace slashes, for example
`/api/v4/projects/group%2Fproject`. If such a request is rejected for an
encoded slash, the GitLab provider profile for that host is missing
`allow_encoded_slash: true`. Fix the profile; do not alter the URL encoding.
