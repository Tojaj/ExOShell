# Google Workspace OAuth

`exoshell-gws-cli` provides OAuth credentials to the Google Workspace CLI. The
sandbox receives placeholders for the client ID, client secret, and refresh
token; OpenShell substitutes the secret values only in OAuth token request
bodies. GWS 0.22.5 uses `accounts.google.com/o/oauth2/token` through
`yup-oauth2` by default, and `oauth2.googleapis.com/token` when it selects
its proxy-aware refresh path. The profile covers both.

Do not mount the host GWS configuration into the sandbox. When using this
provider, the image helper automatically writes placeholder credentials into
the launcher's `/tmp/gws` tmpfs when all three credential environment values
are non-empty. A partial set fails startup; an absent set skips initialization.
Refresh or replace the provider after reauthorizing on the host with changed scopes.

```bash
openshell provider profile lint -f provider-profiles/provider-gws-cli.yaml
openshell provider profile import -f provider-profiles/provider-gws-cli.yaml
```

```bash
GWS_CREDS="$(gws auth export --unmasked)"
openshell provider create --name exoshell-gws --type exoshell-gws-cli \
  --credential "GWS_CLIENT_ID=$(jq -r .client_id <<<"$GWS_CREDS")" \
  --credential "GWS_CLIENT_SECRET=$(jq -r .client_secret <<<"$GWS_CREDS")" \
  --credential "GWS_REFRESH_TOKEN=$(jq -r .refresh_token <<<"$GWS_CREDS")"
unset GWS_CREDS
```

The provider uses request-body credential rewriting because the GWS CLI ignores
environment-variable authentication while its encrypted credentials file is
present. See [ADR 2](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0002-gws-credentials-via-provider-body-rewrite.md).

Smoke test inside a sandbox launched with `--provider exoshell-gws`:

```bash
gws drive files list --params '{"pageSize":1,"fields":"files(id),nextPageToken"}'
```

`gws auth status` may display placeholder values and can report a valid token
without testing a token exchange. Do not print the provider credential
environment variables.
