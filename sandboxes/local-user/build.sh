#!/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BASE_IMAGE=localhost/exoshell-base:latest
TAG=exoshell-local
USER_UID=
USER_GID=

usage() {
  cat <<'EOF'
Usage: build.sh [--base-image IMAGE] [--tag TAG] [--uid UID] [--gid GID]

Build the local ownership layer; UID and GID default to id -u and id -g.
Explicit IDs must be unsigned decimal integers from 1 through 4294967294.
EOF
}

validate_id() {
  local option="$1" value="$2"
  # Explicit digit sets stay ASCII-only; the capture drops leading zeros and
  # bounds the length, so the arithmetic sees no octal or overflow.
  if [[ ! "$value" =~ ^0*([123456789][0123456789]{0,9})$ ]] \
      || (( BASH_REMATCH[1] > 4294967294 )); then
    echo "error: $option requires a decimal ID from 1 through 4294967294" >&2
    return 2
  fi
  printf '%s\n' "${BASH_REMATCH[1]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-image)
      [[ $# -ge 2 ]] || { echo "error: --base-image requires a value" >&2; exit 2; }
      BASE_IMAGE="$2"
      shift 2
      ;;
    --tag)
      [[ $# -ge 2 ]] || { echo "error: --tag requires a value" >&2; exit 2; }
      TAG="$2"
      shift 2
      ;;
    --uid)
      [[ $# -ge 2 ]] || { echo "error: --uid requires a value" >&2; exit 2; }
      USER_UID="$(validate_id --uid "$2")"
      shift 2
      ;;
    --gid)
      [[ $# -ge 2 ]] || { echo "error: --gid requires a value" >&2; exit 2; }
      USER_GID="$(validate_id --gid "$2")"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

USER_UID="$(validate_id --uid "${USER_UID:-$(id -u)}")"
USER_GID="$(validate_id --gid "${USER_GID:-$(id -g)}")"

exec podman build \
  --build-arg "BASE_IMAGE=$BASE_IMAGE" \
  --build-arg "USER_UID=$USER_UID" \
  --build-arg "USER_GID=$USER_GID" \
  --tag "$TAG" \
  "$ROOT"
