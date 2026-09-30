#!/usr/bin/bash
# Public entry point for the portable OpenShell agent launcher.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$ROOT/scripts/exoshell_agent.py" "$@"
