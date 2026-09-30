#!/usr/bin/bash
# Build the generic workload and machine-local ownership layers.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
podman build -t exoshell-base "$ROOT/sandboxes/exoshell-base"
"$ROOT/sandboxes/local-user/build.sh"
