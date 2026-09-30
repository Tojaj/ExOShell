# Local user image

This thin, machine-local layer changes the community `sandbox` account to the
current host UID/GID. That lets a rootless Podman sandbox write files in the
host share without putting personal identity values in committed Dockerfiles.

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
