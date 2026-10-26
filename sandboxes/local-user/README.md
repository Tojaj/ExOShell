# Local user image

This thin, machine-local layer changes the community `sandbox` account to the
current host UID/GID by default. That lets a rootless Podman sandbox write files
in the host share without putting personal identity values in committed Dockerfiles.

Build `exoshell-base` (and any optional derived base) first, then run:

```bash
./sandboxes/local-user/build.sh
```

The default result is `localhost/exoshell-local:latest`. To layer over another
image or choose a different local tag:

```bash
./sandboxes/local-user/build.sh \
  --base-image localhost/example-derived:latest \
  --tag example-local
```

If the host IDs cannot be represented in the rootless user namespace, select
mapped image IDs explicitly:

```bash
./sandboxes/local-user/build.sh --uid 1000 --gid 1000
```

Configure the gateway's Podman driver with `userns = "keep-id:uid=1000,gid=1000"`
to match those image IDs instead of bare `keep-id`. This maps the host user to
`sandbox`: shared files retain host ownership even though the numeric IDs differ
inside the sandbox. The setting applies gateway-wide and must match its images.
Each option defaults independently to `id -u` or `id -g`; accepted IDs are
unsigned decimal integers from 1 through 4294967294 (root and the reserved u32
maximum are rejected). See [ADR-0045](../../adrs/adr0045-explicit-local-image-identity.md).
