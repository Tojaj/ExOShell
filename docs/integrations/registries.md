# Opt-in package registries

*Run these commands on the gateway host, from your ExOShell checkout: the paths
are relative to it. Blocks marked as sandbox commands run inside a sandbox.*

Eight independent, credential-free profiles grant package or container image
downloads and metadata lookups over HTTPS. Ubuntu APT also supports HTTP for
stock source configurations. None is attached by default or grants publishing
access:

| Profile / instance | Public endpoints | Client operations |
| --- | --- | --- |
| `exoshell-npm-registry-ro` | `registry.npmjs.org`, `nodejs.org` (`/download/release/**`) | npm install/update, search, scoped audit requests and Node runtime downloads |
| `exoshell-pypi-packages-ro` | `pypi.org`, `files.pythonhosted.org` | pip/uv indexes, metadata and downloads |
| `exoshell-go-modules-ro` | `proxy.golang.org`, `sum.golang.org`, `go.dev` (`/dl/**`), `dl.google.com` (`/go/**`) | Go runtime downloads, proxy resolution and checksum verification |
| `exoshell-cargo-crates-ro` | `index.crates.io`, `static.crates.io`, `crates.io` | Cargo index, downloads, search and metadata |
| `exoshell-ubuntu-apt-ro` | `archive.ubuntu.com`, `security.ubuntu.com`, `ports.ubuntu.com`, `old-releases.ubuntu.com` | APT indexes and package downloads over HTTP/HTTPS |
| `exoshell-ghcr-registry-ro` | `ghcr.io`, `pkg-containers.githubusercontent.com` | Public OCI image and artifact reads by agents, `curl`, `oras`, `skopeo`, and Python tools |
| `exoshell-dockerhub-registry-ro` | `registry-1.docker.io`, `auth.docker.io`, `production.cloudfront.docker.com`, `docker-images-prod.6aa30f8b08e16409b46e0173d6de2f56.r2.cloudflarestorage.com` | Public OCI image and artifact reads by agents, `curl`, `oras`, `skopeo`, and Python tools |
| `exoshell-quay-registry-ro` | `quay.io`, `cdn.quay.io`, `cdn01.quay.io` through `cdn06.quay.io` | Public OCI image and artifact reads by agents, `curl`, `oras`, `skopeo`, and Python tools |

All eight allow GET/HEAD/OPTIONS; npm alone also allows POST to
`/-/npm/v1/security/advisories/bulk` and `/-/npm/v1/security/audits/quick`.
Publishing, login, and unrelated POST/PUT/PATCH/DELETE requests are not granted.

`uvx`/pip dependency downloads from PyPI, including Python MCP server
installation, require the `exoshell-pypi-packages-ro` instance. Having uv in
the image does not grant PyPI access.

Import and create only the ecosystems needed by a project. For each desired
name below (for example `exoshell-npm-registry-ro`), run:

```bash
openshell provider profile lint -f provider-profiles/provider-npm-registry.yaml
openshell provider profile import -f provider-profiles/provider-npm-registry.yaml
openshell provider create --name exoshell-npm-registry-ro --type exoshell-npm-registry-ro
```

These profiles require no credentials. Do not supply a dummy credential,
`--runtime-credentials`, or `--from-existing` for them.

For PyPI, Go, Cargo, and GHCR, select the file and ID independently:

| Profile file under `provider-profiles/` | Profile ID / instance |
| --- | --- |
| `provider-pypi-packages.yaml` | `exoshell-pypi-packages-ro` |
| `provider-go-modules.yaml` | `exoshell-go-modules-ro` |
| `provider-cargo-crates.yaml` | `exoshell-cargo-crates-ro` |
| `provider-ghcr-registry.yaml` | `exoshell-ghcr-registry-ro` |

Lint/import the selected file, then create with `--name <instance> --type <id>`.
For the two additional container registries:

```bash
openshell provider profile lint -f provider-profiles/provider-dockerhub-registry.yaml
openshell provider profile import -f provider-profiles/provider-dockerhub-registry.yaml
openshell provider create --name exoshell-dockerhub-registry-ro --type exoshell-dockerhub-registry-ro

openshell provider profile lint -f provider-profiles/provider-quay-registry.yaml
openshell provider profile import -f provider-profiles/provider-quay-registry.yaml
openshell provider create --name exoshell-quay-registry-ro --type exoshell-quay-registry-ro
```

These profiles have no credential discovery. They compose with an agent's
inference provider; their names select provider *instances*, not profile files.

### pre-commit runtime setup

Attach npm, PyPI and Go alongside the inference and source-control providers
when hooks use those ecosystems. For example:

```bash
openshell provider profile lint -f provider-profiles/provider-go-modules.yaml
openshell provider profile import -f provider-profiles/provider-go-modules.yaml
openshell provider create --name exoshell-go-modules-ro --type exoshell-go-modules-ro

./run-exoshell-agent.sh --policy policies/policy.yaml --agent codex \
  --provider exoshell-codex --provider exoshell-github \
  --provider exoshell-npm-registry-ro --provider exoshell-pypi-packages-ro \
  --provider exoshell-go-modules-ro .
```

Create the other instances first using the instructions above. CLI provider
options replace the configured list, so include every instance needed for that
session. For repeat use, add the ecosystem instances to the common `providers`
array in `.exoshell.local.toml`; an existing npm/PyPI selection also needs
`exoshell-go-modules-ro` for Go hooks such as gitleaks.

[pre-commit's Go installer](https://raw.githubusercontent.com/pre-commit/pre-commit/main/pre_commit/languages/golang.py)
queries `go.dev/dl/?mode=json` when resolving the default Go version and fetches
archives from `dl.google.com/go/`.
[nodeenv](https://raw.githubusercontent.com/ekalinin/nodeenv/master/nodeenv.py)
fetches Node metadata and archives from `nodejs.org/download/release/`.
The npm and Go profiles allow GET/HEAD/OPTIONS on these paths, with enforced
HTTP inspection. The Go archive path selector also avoids an equal-specificity
conflict with the shared baseline's `**.google.com` audit endpoint.

Both profiles include the base image's uv-managed Python interpreters and
pre-commit's downloaded Node or Go executables under
`/sandbox/.cache/pre-commit/repo*/`. If `PRE_COMMIT_HOME` or `XDG_CACHE_HOME`
relocates that cache, adapt the executable patterns in a custom profile.
Other runtime mirrors and unofficial Node builds need separately reviewed
endpoints. These profiles grant network access; runtime and cache directories
must also be writable under the selected filesystem policy.

For profiles already imported on the host, import is create-only. Export each
profile, copy the corresponding repository definition's description, endpoints
and binaries into the exported document while preserving its `resource_version`
and other deployment metadata, then lint and update it:

```bash
openshell provider profile export exoshell-npm-registry-ro -o yaml > /tmp/exoshell-npm-registry-ro.yaml
openshell provider profile export exoshell-go-modules-ro -o yaml > /tmp/exoshell-go-modules-ro.yaml
# Edit the exported documents as described above before running these commands.
openshell provider profile lint -f /tmp/exoshell-npm-registry-ro.yaml
openshell provider profile lint -f /tmp/exoshell-go-modules-ro.yaml
openshell provider profile update exoshell-npm-registry-ro -f /tmp/exoshell-npm-registry-ro.yaml
openshell provider profile update exoshell-go-modules-ro -f /tmp/exoshell-go-modules-ro.yaml
```

Updates affect every instance of that profile and reach attached running
sandboxes on their next configuration sync. Inspect the effective policy with
`openshell policy get <sandbox> --full` before retrying hook installation.
See [profile update instructions](../customize/providers.md#lint-and-import-profiles).

For a temporary live network grant, `openshell policy update` accepts multiple
`--add-endpoint` flags only when `--rule-name` is omitted; a named update accepts
one endpoint. A broad enforced `dl.google.com` endpoint may conflict with the
baseline Google audit rule, so prefer the path-scoped profile update above.

### Ubuntu APT

```bash
openshell provider profile lint -f provider-profiles/provider-ubuntu-apt.yaml
openshell provider profile import -f provider-profiles/provider-ubuntu-apt.yaml
openshell provider create --name exoshell-ubuntu-apt-ro --type exoshell-ubuntu-apt-ro
```

Attach the instance alongside the agent's inference provider:

```bash
./run-exoshell-agent.sh --policy policies/policy.yaml --agent codex \
  --provider exoshell-codex --provider exoshell-ubuntu-apt-ro \
  . -- exec 'reply with OK'
```

CLI provider options replace the configured list; include any other instances
needed for that launch. For repeat use, add `exoshell-ubuntu-apt-ro` to the common
`providers` array in `.exoshell.local.toml`.

The profile covers `/ubuntu/**` on the main, security and old-release archives,
and `/ubuntu-ports/**` on the ports archive, on ports 80 and 443. These paths
include signed release metadata, package indexes, by-hash files and `.deb`
artifacts. See Ubuntu's [package archive documentation](https://documentation.ubuntu.com/project/how-ubuntu-is-made/concepts/package-archive/),
[ports archive](https://ports.ubuntu.com/ubuntu-ports/), and
[old-release source configuration](https://help.ubuntu.com/community/EOLUpgrades).
APT uses GET; no upload or authentication endpoints are needed. Package paths
use ordinary slashes, so `allow_encoded_slash` remains disabled. Country mirrors,
PPAs, Ubuntu Pro/ESM and third-party repositories need separately reviewed
profiles and client configuration; attaching this provider does not change
APT sources.

The binary list includes `apt`, `apt-get`, their resolved HTTP/HTTPS download
helper, all three agents and `curl`. Smoke-test the grant **inside a sandbox**
that attaches the instance; the same command run on the host proves nothing,
because the host has its own network access:

```bash
# inside the sandbox
curl --fail --silent --show-error --output /tmp/ubuntu-InRelease \
  http://archive.ubuntu.com/ubuntu/dists/noble/InRelease
```

This grants network access only. The baseline policy keeps `/usr`, `/etc` and
other system paths read-only, and the sandbox runs as `sandbox`. System package
installation also requires appropriate privileges and writable APT/dpkg state
and installation paths. Use a separately configured sandbox policy or add
packages to a derived image as described in [customization](../customize/index.md).

### Container registry details

The `exoshell-ghcr-registry-ro` profile permits agents, `curl`, `oras`, `skopeo`, and Python
to read public GHCR tokens, image manifests, and artifacts. GHCR may redirect blob
downloads to `pkg-containers.githubusercontent.com`. Attach it when running the
base-image version checker inside an OpenShell sandbox; that checker validates
the pinned `uv` source image on GHCR. The profile does not govern image pulls
by the host's container engine. OCI repository names use ordinary slashes in
request paths, so this profile does not enable `allow_encoded_slash`; the
checker's encoded slash is in a token-request query parameter.

The `exoshell-dockerhub-registry-ro` profile permits anonymous token requests to
`auth.docker.io` and image reads from `registry-1.docker.io`, including redirects
to Docker's CloudFront and Cloudflare R2 download hosts. See the
[Docker allowlist](https://docs.docker.com/desktop/enterprise/allow-list/) and
[Docker maintainer confirmation of the R2 host](https://github.com/docker/docs/issues/21960).
The `exoshell-quay-registry-ro` profile covers `quay.io` (including its anonymous token
endpoint) and the seven exact CDN hosts listed in the
[upstream firewall documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/installation_configuration/configuring-firewall).
Both profiles use ordinary slashes in repository paths and leave
`allow_encoded_slash` disabled. Encoded slashes in token and signed-download
query parameters do not require that setting.

All three container registry profiles support the same clients and require no
login. They grant public metadata, manifests, configuration blobs, and image
layers; private image authentication is not configured. Docker Hub's anonymous
pull limits still apply. These grants control requests made inside the sandbox,
not image pulls made by the host or gateway container engine.

The base image supplies Skopeo through its distribution package. After rebuilding
the base and derived image layers, inspect a public image in a sandbox with the
matching provider attached:

```bash
# inside the sandbox
# exoshell-dockerhub-registry-ro
skopeo inspect docker://docker.io/library/alpine:latest
oras manifest fetch docker.io/library/alpine:latest

# exoshell-quay-registry-ro
skopeo inspect docker://quay.io/prometheus/busybox:latest
oras manifest fetch quay.io/prometheus/busybox:latest

# exoshell-ghcr-registry-ro
skopeo inspect docker://ghcr.io/astral-sh/uv:0.12.22
```

To verify layer downloads and CDN redirects, copy one of those images to a
writable local OCI layout in the same sandbox, for example:

```bash
# inside the sandbox
skopeo copy docker://docker.io/library/alpine:latest oci:/tmp/alpine-smoke:latest
```

For repeat use, add the selected instance names to the common `providers`
array in `.exoshell.local.toml` so Codex, Claude Code, and OpenCode all get
them. For one run, repeat `--provider` for **every** desired instance, including
the inference provider: CLI options replace the complete configured list.

```bash
./run-exoshell-agent.sh --policy policies/policy.yaml --agent codex \
  --provider exoshell-codex --provider exoshell-dockerhub-registry-ro --provider exoshell-quay-registry-ro \
  . -- exec 'reply with OK'
```

Direct OpenShell launches can also attach them independently:

```bash
openshell sandbox create --from localhost/exoshell-local:latest \
  --policy policies/policy.yaml --provider exoshell-codex --provider exoshell-npm-registry-ro \
  -- codex
```

Add the workspace mount and image startup command as described in the
[image guide](https://github.com/Tojaj/ExOShell/blob/main/sandboxes/exoshell-base/README.md) when working on a host project.
The base image supplies npm, uv/uvx and the agents; it does not install Go or
Cargo. Go hooks can bootstrap Go as described above. For other uses, install
the tools in a derived image and check their
kernel-resolved executable paths against the profile `binaries` list (for
example, `readlink -f "$(command -v go)"`). OpenShell matches the resolved
executable and its ancestors, not a package-manager script named in argv.
For npm, that executable is `/usr/bin/node`; for Python it may be a uv-managed
interpreter under `/sandbox/.uv/python/`.

To use an enterprise proxy, mirror, or private registry, copy the relevant
profile YAML under a new filename, change `id`, `display_name` and the endpoint
host(s) to the actual service, set origin metadata to your own source, and
lint/import/create a new instance from it.
Configure the corresponding npm, pip/uv, Go, or Cargo client to use that
endpoint separately; attaching a provider does not reconfigure the client.
Some ecosystems require separate index, download, and checksum hosts. Add only
those observed and required, and bind credentials explicitly for authenticated
registries. Review the **entire** effective sandbox policy and **all** attached
providers (for example with `openshell sandbox get <name> --policy-only`) for
grants to public registry hosts: attaching only a private clone excludes its
public counterpart only if no other layer grants it. To avoid Go's default
direct-VCS fallback, set `GOPROXY=https://proxy.golang.org` (without `,direct`)
and review `GOPRIVATE`/`GOSUMDB` for the modules in use. Git dependencies and
runtime installers beyond the Node and Go paths above are not covered.
Maven/Gradle, NuGet, RubyGems, and
Composer can have separate profiles later. See
[ADR 24](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0024-opt-in-package-registry-providers.md).
