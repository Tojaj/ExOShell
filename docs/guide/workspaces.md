# Projects and workspaces

The project argument selects what the sandbox can see. This page covers the
three choices: one project, a larger source tree, or no host project at all.

## Share one project

The project argument is a path on the host, not a path inside the sandbox. It
must name an existing directory. Absolute paths, paths relative to the host
shell's current directory, and the current directory itself are accepted:

```bash
# All three launch Claude in the current host directory.
./run-exoshell-agent.sh --agent claude "$(pwd)"
./run-exoshell-agent.sh --agent claude .
./run-exoshell-agent.sh --agent claude
```

When no project argument is provided, the launcher uses the host shell's
current working directory. It resolves the path, including symlinks, before
creating the sandbox.

Without a configured `host_share` or `--host-share`, the project directory is
itself mounted at `/workspace`, and the agent starts in `/workspace`. For
example, host project `/home/me/src/example` becomes `/workspace` in the
sandbox.

`/sandbox` is the sandbox user's home and agent runtime-state area; host
project sources are mounted under `/workspace`, not `/sandbox`.

!!! warning "The agent can change everything you share"
    The mount is writable, so the agent can create, modify, and delete any file
    below it, and those changes stay on the host after the sandbox is deleted.
    Share the narrowest directory that the task needs, and keep the work on a
    branch you can discard.

## Share a larger source tree

When a larger host share is configured, the project must be that directory or
one of its descendants. The relative layout is preserved below `/workspace`:

```text
Host share:      /home/me/src
Host project:    /home/me/src/example
Sandbox mount:   /workspace
Agent starts in: /workspace/example
```

The same can be selected for one invocation:

```bash
./run-exoshell-agent.sh \
  --agent claude \
  --host-share /home/me/src \
  /home/me/src/example
```

The launcher rejects a project outside the selected host share. A host share
widens the writable mount from one project to the whole tree, so the warning
above applies to every repository below it.

## Work without a host project

For a disposable workspace without host project or kubeconfig mounts, pass
`--no-share`. The agent starts in the image's writable `/workspace`, where it
can clone a repository and work entirely inside the sandbox:

```bash
./run-exoshell-agent.sh --no-share --policy policies/policy.yaml \
  -- "Clone https://git.example.com/example/project.git into /workspace/project and inspect it"
```

`--no-share` suppresses configured `host_share` and `kubeconfig` paths, even
when they do not exist. It rejects an explicit `--host-share`, `--kubeconfig`,
or positional project. Configuration discovery, providers, and policy selection
still apply. Git identity comes only from global host configuration when both
name and email are present; otherwise configure it inside the sandbox as needed.
The `/tmp/gws` tmpfs remains available, and OpenShell manages its own internal
storage. Cloned repositories and work are discarded when the sandbox is deleted;
pass `--keep` to retain them. See
[ADR-0037](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0037-optional-host-sharing.md).

## Mount a kubeconfig

`--kubeconfig /path/to/config`, or the TOML `kubeconfig` setting, mounts one
host kubeconfig file read-only at `/sandbox/.kube/config` and sets the
sandbox's `KUBECONFIG` to that path. The image provides `kubectl` and `oc`.
Nothing is mounted when the setting is omitted; `--no-kubeconfig` suppresses a
configured path for one launch.

!!! warning "A mounted kubeconfig is readable by the agent"
    Unlike API keys supplied by providers, a kubeconfig is a real file in the
    sandbox: its tokens, client certificates, and cluster endpoints are
    readable by anything running there, and the read-only mount prevents
    modification, not disclosure. Mount a kubeconfig limited to the clusters
    and permissions the task needs, and omit it otherwise.

Reaching a cluster also needs a [policy](../customize/policies.md) entry for the
API server endpoint that lists the `kubectl` or `oc` binary. The portable
baseline contains no cluster endpoint, so the mount alone grants no access.

## SELinux labels

On SELinux-enabled hosts, the launcher requests a shared Podman bind mount and
Podman labels the mounted tree when the sandbox starts. If a file is downloaded
elsewhere on the host and then moved or renamed into the project while the
sandbox is running, its original SELinux label moves with it and it may be
inaccessible from the sandbox. Relabel such a file using the project directory
as the reference:

```bash
chcon --reference=. path/to/file
```
