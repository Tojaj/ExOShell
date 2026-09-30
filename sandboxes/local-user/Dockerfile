# syntax=docker/dockerfile:1

# Local-only ownership layer. Use build.sh so the IDs come from the host.
ARG BASE_IMAGE=localhost/exoshell-base:latest
FROM ${BASE_IMAGE}

USER root

ARG USER_UID
ARG USER_GID
# Remap community `sandbox` to the host UID/GID. Bare `userns=keep-id` keeps
# those same numbers; it does not map the host user onto this account.
# See adrs/adr0015-host-uid-remap-not-keep-id.md.
# Community `base` omits /usr/sbin from PATH. Ubuntu Noble's `ubuntu` account
# occupies 1000:1000; delete any non-sandbox occupant before remapping.
RUN test -n "${USER_UID}" \
    && test -n "${USER_GID}" \
    && existing_user="$(getent passwd "${USER_UID}" | cut -d: -f1 || true)" \
    && if [ -n "${existing_user}" ] && [ "${existing_user}" != sandbox ]; then \
         /usr/sbin/userdel -r "${existing_user}" || /usr/sbin/userdel "${existing_user}"; \
       fi \
    && existing_group="$(getent group "${USER_GID}" | cut -d: -f1 || true)" \
    && if [ -n "${existing_group}" ] && [ "${existing_group}" != sandbox ]; then \
         /usr/sbin/groupdel "${existing_group}"; \
       fi \
    && /usr/sbin/groupmod --gid "${USER_GID}" sandbox \
    && /usr/sbin/usermod --uid "${USER_UID}" --gid "${USER_GID}" sandbox \
    && chown -R sandbox:sandbox /sandbox /workspace \
    && chown sandbox:sandbox /etc/glab-cli/config.yml

WORKDIR /sandbox
USER sandbox

ENTRYPOINT ["/bin/bash"]
