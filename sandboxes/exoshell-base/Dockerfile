# syntax=docker/dockerfile:1

# Generic OpenShell sandbox image: community `base` plus the extra CLIs
# this setup runs. Reuses community user `sandbox` (home /sandbox).
#
# Build (Podman):  podman build -t exoshell-base .
# OpenShell:       openshell sandbox create --from localhost/exoshell-base:latest ...
# OpenShell 0.1.0 `--from` accepts a built image reference, not a build directory.
#
# Pin ARG versions (agent CLIs and extra tools). Bump and rebuild to upgrade.

ARG BASE_IMAGE=ghcr.io/nvidia/openshell-community/sandboxes/base:latest
ARG UV_VERSION=0.12.19

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv-source
FROM ${BASE_IMAGE}

USER root

# BuildKit and Podman populate this from an explicit target platform.
ARG TARGETARCH

ARG GWS_VERSION=0.22.5
ARG CODEX_VERSION=0.159.2
ARG CLAUDE_VERSION=2.1.283
ARG OPENCODE_VERSION=1.18.33
ARG GLAB_VERSION=1.119.0
ARG OC_VERSION=4.15.59
ARG ORAS_VERSION=1.3.4
ARG YQ_VERSION=4.53.6
ARG TKN_VERSION=0.46.1
ARG PRE_COMMIT_VERSION=4.6.2
ARG AST_GREP_VERSION=0.45.3

ENV DEBIAN_FRONTEND=noninteractive

# Search and JSON tools via apt. Debian names the fd binary fdfind, so add
# the customary fd command. curl/ca-certificates/git/node/uv are in `base`.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fd-find \
        jq \
        ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sfn /usr/bin/fdfind /usr/local/bin/fd

# ast-grep provides structural code search and rewriting. Its `sg` alias
# conflicts with the system's /usr/bin/sg, so install under a separate prefix
# and expose only the unambiguous command on PATH.
RUN npm install -g --prefix /opt/ast-grep "@ast-grep/cli@${AST_GREP_VERSION}" \
    && ln -s /opt/ast-grep/bin/ast-grep /usr/local/bin/ast-grep \
    && npm cache clean --force \
    && ast-grep --version | grep -F "${AST_GREP_VERSION}"

# gws + Node package tree at the policy path /usr/local/lib/node_modules/@googleworkspace/**
RUN npm install -g "@googleworkspace/cli@${GWS_VERSION}" \
    && npm cache clean --force

# Overlay newer Codex on the same npm layout as community `base`.
# `_provider_openai` allows /usr/bin/codex, /usr/local/bin/codex, and
# /usr/lib/node_modules/@openai/** (resolved exe path, not the PATH shim).
RUN npm install -g "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force

# Overlay newer OpenCode on the same npm layout as community `base`.
# Policy matches PATH shims and the npm tree (native ELF is
# opencode-ai/bin/opencode.exe; older releases used bin/.opencode).
RUN npm install -g "opencode-ai@${OPENCODE_VERSION}" \
    && npm cache clean --force \
    && oc_bin="$(command -v opencode)" \
    && [ -n "$oc_bin" ] \
    && if [ "$oc_bin" != /usr/local/bin/opencode ]; then ln -sfn "$oc_bin" /usr/local/bin/opencode; fi \
    && if [ "$oc_bin" != /usr/bin/opencode ]; then ln -sfn "$oc_bin" /usr/bin/opencode; fi \
    && opencode --version | grep -F "${OPENCODE_VERSION}"

# Overlay pinned Claude Code via the native installer (npm is deprecated and
# would land under /usr/lib/node_modules/@anthropic-ai/**, which profiles omit).
# Community `base` copies the same binary to /usr/local/bin/claude.
# Do not set DISABLE_* until after this RUN — the installer honors them and
# would keep the older binary from `base`.
RUN curl -fsSL https://claude.ai/install.sh | bash -s -- "${CLAUDE_VERSION}" \
    && install -m 0755 /root/.local/bin/claude /usr/local/bin/claude \
    && ln -sfn /usr/local/bin/claude /usr/bin/claude \
    && /usr/local/bin/claude --version | grep -F "${CLAUDE_VERSION}"

# Keep the Claude pin at runtime (writable home would otherwise auto-update).
ENV DISABLE_AUTOUPDATER=1 \
    DISABLE_UPDATES=1

# Policy and `uvx --from git+https://…` need `uvx`.
COPY --from=uv-source /uv /uvx /usr/local/bin/

# glab, oc+kubectl, oras, yq, tkn (+ kubectl-tkn plugin). Plain Podman builds
# do not inject TARGETARCH, so use the native Debian architecture in that case.
RUN set -eux; \
    arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "$arch" in \
      amd64) goarch=amd64; xarch=x86_64; oc_dir=x86_64 ;; \
      arm64) goarch=arm64; xarch=aarch64; oc_dir=aarch64 ;; \
      *) echo "unsupported TARGETARCH=$arch" >&2; exit 1 ;; \
    esac; \
    tmp=$(mktemp -d); \
    curl -fsSL "https://gitlab.com/gitlab-org/cli/-/releases/v${GLAB_VERSION}/downloads/glab_${GLAB_VERSION}_linux_${goarch}.tar.gz" \
      -o "$tmp/glab.tar.gz"; \
    tar -xzf "$tmp/glab.tar.gz" -C "$tmp"; \
    install -m 0755 "$tmp/bin/glab" /usr/bin/glab; \
    curl -fsSL "https://mirror.openshift.com/pub/openshift-v4/${oc_dir}/clients/ocp/${OC_VERSION}/openshift-client-linux.tar.gz" \
      -o "$tmp/oc.tar.gz"; \
    tar -xzf "$tmp/oc.tar.gz" -C "$tmp" oc kubectl; \
    install -m 0755 "$tmp/oc" /usr/bin/oc; \
    install -m 0755 "$tmp/kubectl" /usr/bin/kubectl; \
    ln -sfn /usr/bin/kubectl /usr/local/bin/kubectl; \
    curl -fsSL "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_${goarch}.tar.gz" \
      -o "$tmp/oras.tar.gz"; \
    tar -xzf "$tmp/oras.tar.gz" -C "$tmp" oras; \
    install -m 0755 "$tmp/oras" /usr/local/bin/oras; \
    ln -sfn /usr/local/bin/oras /usr/bin/oras; \
    curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${goarch}" \
      -o /usr/bin/yq; \
    chmod 0755 /usr/bin/yq; \
    curl -fsSL "https://github.com/tektoncd/cli/releases/download/v${TKN_VERSION}/tkn_${TKN_VERSION}_Linux_${xarch}.tar.gz" \
      -o "$tmp/tkn.tar.gz"; \
    tar -xzf "$tmp/tkn.tar.gz" -C "$tmp" tkn; \
    install -m 0755 "$tmp/tkn" /usr/local/bin/tkn; \
    ln -sfn /usr/local/bin/tkn /usr/bin/tkn; \
    ln -sfn /usr/local/bin/tkn /usr/local/bin/kubectl-tkn; \
    ln -sfn /usr/local/bin/tkn /usr/bin/kubectl-tkn; \
    rm -rf "$tmp"

# pre-commit into the image-wide venv (on PATH as /sandbox/.venv/bin)
RUN uv pip install --python /sandbox/.venv/bin/python "pre-commit==${PRE_COMMIT_VERSION}" \
    && ln -sfn /sandbox/.venv/bin/pre-commit /usr/local/bin/pre-commit \
    && ln -sfn /sandbox/.venv/bin/pre-commit /usr/bin/pre-commit \
    && uv cache clean

# Install the upstream skill from this exact pinned glab binary. The companion
# skills document ExOShell's provider and policy behavior without forking it.
RUN HOME=/sandbox /usr/bin/glab skills install glab --global

# Policy-path aliases: Landlock matches these exact paths, not $PATH lookups.
RUN chmod 0755 /usr/local/bin/uv /usr/local/bin/uvx \
    && ln -sfn /usr/local/bin/uv /usr/bin/uv \
    && ln -sfn /usr/local/bin/uvx /usr/bin/uvx \
    && ln -sfn /usr/local/bin/python3 /usr/bin/python3

# Community `base` already has user `sandbox` (home /sandbox) and shell init.
# A thin local derivative changes only this account's numeric UID/GID to match
# the owner of the host share. OpenShell still uses /sandbox as the Podman
# workspace; create only the paths that must be writable without rewriting
# ownership metadata for the inherited home directory.
RUN install -d -o sandbox -g sandbox \
        /sandbox/.kube /sandbox/.codex /sandbox/.claude \
        /sandbox/.claude/skills /sandbox/.config/opencode \
        /sandbox/.cache/opencode /sandbox/.local/share/opencode /workspace

ENV GLAB_CONFIG_DIR=/etc/glab-cli \
    GLAB_CHECK_UPDATE=false

# Local configuration is intentionally last: changing it must not invalidate
# cached package installs or downloaded CLI binaries.
# System-level Codex defaults are independent of disposable user state.
COPY --chmod=0644 codex.config.toml /etc/codex/config.toml
COPY --chmod=0755 exoshell-agent /usr/local/bin/exoshell-agent
# Global defaults keep the image-pinned OpenCode version from updating while
# allowing project configuration to override them.
COPY --chown=sandbox:sandbox --chmod=0644 opencode.json /sandbox/.config/opencode/opencode.json
COPY --chown=sandbox:sandbox --chmod=0644 tui.json /sandbox/.config/opencode/tui.json
COPY --chown=sandbox:sandbox --chmod=0644 opencode-instructions/ /sandbox/.config/opencode/instructions/
# User-scope defaults avoid the exclusive-control behavior of managed MCP
# configuration while making the provider-backed endpoint available.
COPY --chown=sandbox:sandbox --chmod=0644 claude.config.json /sandbox/.claude.json
# Register the public GitLab host without storing credentials. glab requires
# config.yml to be exactly 0600, so it must be readable by the sandbox user.
# The root-owned directory prevents glab from atomically replacing this
# image-provided template; provider placeholders remain the only credentials.
COPY --chown=sandbox:sandbox skills/ /sandbox/.agents/skills/
COPY --chown=sandbox:sandbox glab-config.yml /etc/glab-cli/config.yml
RUN chmod 0600 /etc/glab-cli/config.yml \
    && for skill in /sandbox/.agents/skills/*/; do \
         [ -d "$skill" ] || continue; \
         ln -sfn "$skill" "/sandbox/.claude/skills/$(basename "$skill")"; \
       done

WORKDIR /sandbox
USER sandbox

# OpenShell replaces ENTRYPOINT/CMD with the supervisor. Pass the agent after `--`.
ENTRYPOINT ["/bin/bash"]
