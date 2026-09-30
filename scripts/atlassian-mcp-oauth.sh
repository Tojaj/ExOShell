#!/usr/bin/env bash
# OAuth 2.1 helper for Atlassian Rovo MCP.
#
# Performs the authorization code flow with PKCE (S256) against the MCP
# server's own OAuth authorization server at mcp.atlassian.com.
#
# Usage:
#   ./scripts/atlassian-mcp-oauth.sh sync [--provider NAME]
#   ./scripts/atlassian-mcp-oauth.sh status [--provider NAME]
#   ./scripts/atlassian-mcp-oauth.sh revoke [--provider NAME]
#
# sync creates or updates the named OpenShell provider without exposing the
# access token to the calling shell. State (client_id, refresh_token) is kept
# on the host in STATE_FILE, keyed by provider name.

set -euo pipefail

MCP_BASE="https://mcp.atlassian.com"
MCP_RESOURCE="$MCP_BASE/v2/mcp"
RESOURCE_METADATA_URL="$MCP_BASE/.well-known/oauth-protected-resource/v2/mcp"
STATE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/openshell"
STATE_FILE="$STATE_DIR/atlassian-mcp-oauth.json"
CALLBACK_PORT="${ATLASSIAN_OAUTH_PORT:-8793}"
DEFAULT_PROVIDER="atlassian-mcp"
PROVIDER_NAME="$DEFAULT_PROVIDER"

die()  { printf '%s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*" >&2; }

require_cmd() {
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || die "required command not found: $cmd"
  done
}

# --- helpers ---

base64url_encode() {
  openssl base64 -A | tr '+/' '-_' | tr -d '='
}

generate_code_verifier() {
  openssl rand 32 | base64url_encode
}

generate_code_challenge() {
  printf '%s' "$1" | openssl dgst -sha256 -binary | base64url_encode
}

migrate_state() {
  [[ -f "$STATE_FILE" ]] || return 0
  jq -e '.providers | type == "object"' "$STATE_FILE" >/dev/null 2>&1 && return

  local tmp="$STATE_FILE.tmp.$$"
  jq --arg provider "$DEFAULT_PROVIDER" '{providers: {($provider): .}}' "$STATE_FILE" > "$tmp" \
    || die "failed to migrate OAuth state at $STATE_FILE"
  mv "$tmp" "$STATE_FILE"
  chmod 600 "$STATE_FILE"
  info "migrated OAuth state for provider: $DEFAULT_PROVIDER"
}

read_state() {
  if [[ -f "$STATE_FILE" ]]; then
    jq -r --arg provider "$PROVIDER_NAME" --arg key "$1" \
      '.providers[$provider][$key] // empty' "$STATE_FILE" 2>/dev/null || true
  fi
}

write_state() {
  mkdir -p "$STATE_DIR"
  local tmp="$STATE_FILE.tmp.$$"
  if [[ -f "$STATE_FILE" ]]; then
    jq --arg provider "$PROVIDER_NAME" --arg key "$1" --arg value "$2" \
      '.providers //= {} | .providers[$provider] //= {} | .providers[$provider][$key] = $value' \
      "$STATE_FILE" > "$tmp"
  else
    jq -n --arg provider "$PROVIDER_NAME" --arg key "$1" --arg value "$2" \
      '{providers: {($provider): {($key): $value}}}' > "$tmp"
  fi
  mv "$tmp" "$STATE_FILE"
  chmod 600 "$STATE_FILE"
}

clear_state() {
  [[ -f "$STATE_FILE" ]] || return 0

  local tmp="$STATE_FILE.tmp.$$"
  jq --arg provider "$PROVIDER_NAME" 'del(.providers[$provider])' "$STATE_FILE" > "$tmp"
  if jq -e '.providers | length == 0' "$tmp" >/dev/null; then
    rm -f "$tmp" "$STATE_FILE"
  else
    mv "$tmp" "$STATE_FILE"
    chmod 600 "$STATE_FILE"
  fi
}

# --- OAuth discovery (RFC 9728 two-step) ---

discover() {
  # Step 1: protected resource metadata → real authorization server URL
  local resource_meta as_url
  resource_meta=$(curl -sS "$RESOURCE_METADATA_URL") || die "failed to fetch resource metadata"
  as_url=$(printf '%s' "$resource_meta" | jq -r '.authorization_servers[0] // empty')
  [[ -n "$as_url" ]] || die "no authorization_servers in resource metadata"

  # Step 2: AS metadata
  local as_meta
  as_meta=$(curl -sS "$as_url/.well-known/oauth-authorization-server") || die "failed to fetch AS metadata"
  AUTH_ENDPOINT=$(printf '%s' "$as_meta" | jq -r '.authorization_endpoint')
  TOKEN_ENDPOINT=$(printf '%s' "$as_meta" | jq -r '.token_endpoint')
  REG_ENDPOINT=$(printf '%s' "$as_meta" | jq -r '.registration_endpoint // empty')
  [[ "$AUTH_ENDPOINT" != "null" && -n "$AUTH_ENDPOINT" ]] || die "missing authorization_endpoint in AS metadata"
  [[ "$TOKEN_ENDPOINT" != "null" && -n "$TOKEN_ENDPOINT" ]] || die "missing token_endpoint in AS metadata"
}

# --- dynamic client registration ---

register_client() {
  local reg_url="${REG_ENDPOINT:-$MCP_BASE/v1/register}"
  local resp
  resp=$(curl -sS -X POST "$reg_url" \
    -H "Content-Type: application/json" \
    -d "{
      \"client_name\": \"openshell-atlassian-mcp\",
      \"redirect_uris\": [\"http://127.0.0.1:$CALLBACK_PORT/callback\"],
      \"grant_types\": [\"authorization_code\", \"refresh_token\"],
      \"response_types\": [\"code\"],
      \"token_endpoint_auth_method\": \"none\"
    }") || die "client registration failed"

  CLIENT_ID=$(printf '%s' "$resp" | jq -r '.client_id // empty')
  [[ -n "$CLIENT_ID" ]] || die "registration response missing client_id: $resp"
  write_state client_id "$CLIENT_ID"
  info "registered client: $CLIENT_ID"
}

# --- authorization code flow ---

start_callback_server() {
  AUTHORIZATION_CODE=$(python3 - "$CALLBACK_PORT" <<'PYEOF'
import sys, socket, re
from urllib.parse import unquote

port = int(sys.argv[1])
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(('127.0.0.1', port))
srv.listen(1)
conn, _ = srv.accept()
data = b''
while b'\r\n\r\n' not in data and len(data) < 8192:
    chunk = conn.recv(4096)
    if not chunk:
        break
    data += chunk
text = data.decode('utf-8', errors='replace')
m = re.search(r'[?&]code=([^& ]+)', text)
code = unquote(m.group(1)) if m else ''
body = b'<html><body><h2>Authorization complete.</h2><p>You may close this tab.</p></body></html>'
resp = (b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: '
        + str(len(body)).encode() + b'\r\n\r\n' + body)
conn.sendall(resp)
conn.close()
srv.close()
print(code, end='')
PYEOF
  )
}

do_auth() {
  require_cmd curl jq openssl python3

  discover

  # Register a new client (or reuse existing)
  CLIENT_ID=$(read_state client_id)
  if [[ -z "$CLIENT_ID" ]]; then
    register_client
  else
    info "reusing registered client: $CLIENT_ID"
  fi

  local code_verifier code_challenge state
  code_verifier=$(generate_code_verifier)
  code_challenge=$(generate_code_challenge "$code_verifier")
  state=$(openssl rand -hex 16)

  local encoded_resource encoded_redirect
  encoded_resource=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1],safe=''))" "$MCP_RESOURCE")
  encoded_redirect=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1],safe=''))" "http://127.0.0.1:${CALLBACK_PORT}/callback")

  local auth_url="${AUTH_ENDPOINT}?response_type=code"
  auth_url+="&client_id=${CLIENT_ID}"
  auth_url+="&redirect_uri=${encoded_redirect}"
  auth_url+="&code_challenge=${code_challenge}"
  auth_url+="&code_challenge_method=S256"
  auth_url+="&state=${state}"
  auth_url+="&resource=${encoded_resource}"

  info ""
  info "Open this URL in your browser to authorize:"
  info ""
  info "  $auth_url"
  info ""

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$auth_url" 2>/dev/null &
  fi

  info "Waiting for callback on port $CALLBACK_PORT..."
  start_callback_server

  if [[ -z "${AUTHORIZATION_CODE:-}" ]]; then
    die "did not receive authorization code"
  fi
  info "received authorization code"

  # Exchange code for tokens
  local resp
  resp=$(curl -sS -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=authorization_code" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "code=$AUTHORIZATION_CODE" \
    --data-urlencode "redirect_uri=http://127.0.0.1:$CALLBACK_PORT/callback" \
    --data-urlencode "code_verifier=$code_verifier" \
    --data-urlencode "resource=$MCP_RESOURCE") || die "token exchange failed"

  local access_token refresh_token
  access_token=$(printf '%s' "$resp" | jq -r '.access_token // empty')
  refresh_token=$(printf '%s' "$resp" | jq -r '.refresh_token // empty')
  [[ -n "$access_token" ]] || die "token response missing access_token: $resp"

  if [[ -n "$refresh_token" ]]; then
    write_state refresh_token "$refresh_token"
    info "refresh token stored"
  fi

  write_state last_auth "$(date -Iseconds)"
  printf '%s' "$access_token"
}

# --- token refresh ---

do_refresh() {
  require_cmd curl jq

  discover

  CLIENT_ID=$(read_state client_id)
  [[ -n "$CLIENT_ID" ]] || die "no client_id in state — run 'auth' first"

  local refresh_token
  refresh_token=$(read_state refresh_token)
  [[ -n "$refresh_token" ]] || die "no refresh_token in state — run 'auth' first"

  local resp
  resp=$(curl -sS -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=refresh_token" \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "refresh_token=$refresh_token" \
    --data-urlencode "resource=$MCP_RESOURCE") || die "token refresh failed"

  local access_token new_refresh_token
  access_token=$(printf '%s' "$resp" | jq -r '.access_token // empty')
  new_refresh_token=$(printf '%s' "$resp" | jq -r '.refresh_token // empty')
  if [[ -z "$access_token" ]]; then
    local oauth_error
    oauth_error=$(printf '%s' "$resp" | jq -r '.error // empty')
    if [[ "$oauth_error" == "invalid_grant" ]]; then
      info "stored refresh token was rejected; authorization is required"
      return 2
    fi
    die "refresh response missing access_token${oauth_error:+ (error: $oauth_error)}"
  fi

  # Atlassian rotates refresh tokens — persist the new one
  if [[ -n "$new_refresh_token" ]]; then
    write_state refresh_token "$new_refresh_token"
    info "refresh token rotated and stored"
  fi

  write_state last_refresh "$(date -Iseconds)"
  printf '%s' "$access_token"
}

# --- provider synchronization ---

provider_exists() {
  local providers page_token=""
  while true; do
    if [[ -n "$page_token" ]]; then
      providers=$(openshell provider list -o json --page-token "$page_token") \
        || die "failed to list OpenShell providers"
    else
      providers=$(openshell provider list -o json) || die "failed to list OpenShell providers"
    fi

    # Structured 0.1.0 lists include providers and an opaque next-page token.
    jq -e 'type == "object" and (.providers | type) == "array"
      and (.next_page_token | type) == "string"' >/dev/null <<<"$providers" \
      || die "unexpected response while listing OpenShell providers"

    if jq -e --arg provider "$PROVIDER_NAME" \
      '.providers | any(.[]; .name == $provider)' >/dev/null <<<"$providers"; then
      return 0
    fi
    page_token=$(jq -r '.next_page_token' <<<"$providers")
    [[ -n "$page_token" ]] || return 1
  done
}

confirm_provider_create() {
  [[ -t 0 ]] || die "provider '$PROVIDER_NAME' does not exist; create it interactively or run this script from a terminal"

  local reply
  while true; do
    read -r -p "Provider '$PROVIDER_NAME' does not exist. Create it? [y/N] " reply || exit 1
    case "$reply" in
      [Yy]|[Yy][Ee][Ss]) return ;;
      ""|[Nn]|[Nn][Oo]) die "provider creation declined" ;;
      *) info "please answer yes or no" ;;
    esac
  done
}

store_access_token() {
  local action="$1"
  local access_token="$2"

  if [[ "$action" == "create" ]]; then
    ATLASSIAN_MCP_BEARER_TOKEN="$access_token" \
      openshell provider create --name "$PROVIDER_NAME" --type atlassian-mcp --from-existing
  else
    ATLASSIAN_MCP_BEARER_TOKEN="$access_token" \
      openshell provider update "$PROVIDER_NAME" --from-existing
  fi
}

do_sync() {
  require_cmd curl jq openssl python3 openshell
  migrate_state

  local action access_token
  if provider_exists; then
    action="update"
    if [[ -n "$(read_state client_id)" && -n "$(read_state refresh_token)" ]]; then
      if access_token=$(do_refresh); then
        store_access_token "$action" "$access_token"
        return
      fi
    else
      info "no refresh state for provider '$PROVIDER_NAME'; authorization is required"
    fi
  else
    action="create"
    confirm_provider_create
  fi

  access_token=$(do_auth)
  store_access_token "$action" "$access_token"
}

# --- revoke ---

do_revoke() {
  require_cmd curl jq
  migrate_state

  discover

  CLIENT_ID=$(read_state client_id)
  [[ -n "$CLIENT_ID" ]] || die "no client_id in state — nothing to revoke"

  local refresh_token
  refresh_token=$(read_state refresh_token)
  [[ -n "$refresh_token" ]] || die "no refresh_token in state — nothing to revoke"

  curl -sS -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "token=$refresh_token" \
    --data-urlencode "token_type_hint=refresh_token" \
    --data-urlencode "client_id=$CLIENT_ID" \
    >/dev/null || die "revocation failed"

  clear_state
  info "refresh token revoked and state cleared for provider: $PROVIDER_NAME"
}

# --- status ---

do_status() {
  require_cmd jq
  migrate_state
  if [[ ! -f "$STATE_FILE" ]]; then
    info "no state file found at $STATE_FILE"
    exit 1
  fi
  if [[ -z "$(read_state client_id)" ]]; then
    info "no state found for provider '$PROVIDER_NAME' in $STATE_FILE"
    exit 1
  fi
  info "state file: $STATE_FILE"
  info "provider:     $PROVIDER_NAME"
  info "client_id:    $(read_state client_id)"
  info "has refresh:  $([[ -n "$(read_state refresh_token)" ]] && echo yes || echo no)"
  info "last auth:    $(read_state last_auth)"
  info "last refresh: $(read_state last_refresh)"
}

# --- main ---

COMMAND="sync"
case "${1:-}" in
  sync|status|revoke)
    COMMAND="$1"
    shift
    ;;
  ""|--*) ;;
  *)
    die "unknown command: $1"
    ;;
esac

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)
      [[ $# -ge 2 && -n "$2" ]] || die "--provider requires a name"
      PROVIDER_NAME="$2"
      shift 2
      ;;
    --help|-h)
      cat >&2 <<USAGE
Usage: $0 [sync|status|revoke] [--provider NAME]

Commands:
  sync      Create or update a provider with a current OAuth access token (default)
  status    Show OAuth state for a provider
  revoke    Revoke and clear OAuth state for a provider
USAGE
      exit 0
      ;;
    *) die "unknown option: $1" ;;
  esac
done

case "$COMMAND" in
  sync)   do_sync ;;
  status) do_status ;;
  revoke) do_revoke ;;
esac
