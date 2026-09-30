#!/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BASE_IMAGE=localhost/exoshell-base:latest
TAG=exoshell-local

usage() {
  cat <<'EOF'
Usage: build.sh [--base-image IMAGE] [--tag TAG]

Build the local ownership layer with the current host UID and GID.
EOF
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

exec podman build \
  --build-arg "BASE_IMAGE=$BASE_IMAGE" \
  --build-arg "USER_UID=$(id -u)" \
  --build-arg "USER_GID=$(id -g)" \
  --tag "$TAG" \
  "$ROOT"
