#!/usr/bin/env bash
# Refresh already-imported ExOShell provider profiles from this checkout.
#
# Profile import is create-only, so updating means: export the live profile,
# copy this repository's description/endpoints/binaries over it (keeping
# resource_version and other deployment metadata), lint, and update.
# See providers.md "For profiles already imported on the host".
#
# Run from the repository root on the host (needs the `openshell` CLI and
# python3 with PyYAML — not inside the sandbox):
#
#   ./scripts/update-provider-profiles.sh                          # every imported profile with a repo definition
#   ./scripts/update-provider-profiles.sh exoshell-github-cli      # selected profiles only
#   ./scripts/update-provider-profiles.sh --yes exoshell-npm-registry-ro  # skip confirmation prompts
set -euo pipefail

YES=0
WANT=()
for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) WANT+=("$arg") ;;
  esac
done

if ! command -v openshell >/dev/null 2>&1; then
  echo "error: 'openshell' CLI not found; run this on the host, not in the sandbox" >&2
  exit 1
fi

# Profile IDs default to every imported profile that has a definition here.
if [ "${#WANT[@]}" -eq 0 ]; then
  while IFS= read -r name; do
    [ -n "$name" ] && WANT+=("$name")
  done < <(openshell provider profile list 2>/dev/null | awk 'NR>1 && $1!="" {print $1}')
fi
if [ "${#WANT[@]}" -eq 0 ]; then
  echo "error: no imported profiles found; pass profile IDs explicitly" >&2
  exit 1
fi

repo_file_for() {
  grep -l "^id: $1$" provider-profiles/*.yaml 2>/dev/null | head -n 1
}

merge_profile() {
  python3 - "$1" "$2" "$3" <<'EOF'
import sys
import yaml


class IndentDumper(yaml.SafeDumper):
    # Match the repository style: indented block sequences instead of
    # PyYAML's default indentless ones, so the diff only shows real changes.
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


live_path, repo_path, out_path = sys.argv[1:4]
with open(live_path) as handle:
    live = yaml.safe_load(handle)
with open(repo_path) as handle:
    repo = yaml.safe_load(handle)
for key in ("description", "endpoints", "binaries"):
    if key not in repo:
        raise SystemExit(f"error: {repo_path} has no '{key}' to copy")
    live[key] = repo[key]
with open(out_path, "w") as handle:
    yaml.dump(live, handle, Dumper=IndentDumper, sort_keys=False,
              default_flow_style=False, allow_unicode=True, width=4096)
EOF
}

UPDATED=()
SKIPPED=()
for id in "${WANT[@]}"; do
  repo="$(repo_file_for "$id" || true)"
  if [ -z "$repo" ]; then
    echo "skip: $id has no definition under provider-profiles/ (custom profile?)"
    SKIPPED+=("$id")
    continue
  fi
  work="$(mktemp -d)"
  openshell provider profile export "$id" -o yaml >"$work/live.yaml"
  merge_profile "$work/live.yaml" "$repo" "$work/merged.yaml"
  echo "--- $id ($repo)"
  if cmp -s "$work/live.yaml" "$work/merged.yaml"; then
    echo "note: $id already matches $repo"
    rm -rf "$work"
    continue
  fi
  diff -u "$work/live.yaml" "$work/merged.yaml" || true
  if [ "$YES" -eq 0 ]; then
    read -r -p "update $id from $repo? [y/N] " answer
    case "$answer" in
      y|Y|yes|YES) ;;
      *) echo "skip: $id"; SKIPPED+=("$id"); rm -rf "$work"; continue ;;
    esac
  fi
  openshell provider profile lint -f "$work/merged.yaml" >"$work/lint.log" 2>&1 || {
    # `lint` rejects an ID that is already imported; that is expected when
    # refreshing a profile, so only fail on diagnostics saying anything else.
    if grep -i 'error' "$work/lint.log" | grep -viE 'already exists|lint failed' | grep -q .; then
      cat "$work/lint.log" >&2
      echo "error: lint failed for $id" >&2
      rm -rf "$work"
      exit 1
    fi
    echo "note: lint reports an already-imported ID (expected for updates)"
  }
  openshell provider profile update "$id" -f "$work/merged.yaml"
  UPDATED+=("$id")
  rm -rf "$work"
done

echo "updated: ${UPDATED[*]:-none}; skipped: ${SKIPPED[*]:-none}"
