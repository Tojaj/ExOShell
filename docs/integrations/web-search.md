# Tavily web search

*Run these commands on the gateway host, from your ExOShell checkout: the paths
are relative to it. Blocks marked as sandbox commands run inside a sandbox.*

`exoshell-tavily-search` supplies a Bearer API key to the Tavily search API
for Codex, Claude Code, and OpenCode sandboxes. Tavily fetches upstream
sources server-side and returns their content in the API response, so the
sandbox only ever contacts `api.tavily.com` and needs no direct grant for the
researched URLs. The sandbox receives the `TAVILY_API_KEY` placeholder — the
variable OpenCode websearch looks for — and OpenShell substitutes the real key
only for the bound Tavily endpoint.

For OpenCode, `exoshell-agent` selects `websearch.provider = "tavily"` when
`TAVILY_API_KEY` is non-empty, skipping the provider-selection prompt. This
uses disposable `OPENCODE_CONFIG_CONTENT`, not a project file, and never copies
the key into configuration. An explicit provider or `websearch: false` in that
inline layer is preserved; otherwise this selection overrides file-based search
settings. Without the key, search configuration is unchanged. Bare `opencode`
commands bypass this initialization. Rebuild the base and dependent images to
enable it.

```bash
openshell provider profile lint -f provider-profiles/provider-tavily-search.yaml
openshell provider profile import -f provider-profiles/provider-tavily-search.yaml
```

```bash
read -rsp "Tavily API key: " TAVILY_API_KEY
printf '\n'
export TAVILY_API_KEY
openshell provider create --name exoshell-tavily-search \
  --type exoshell-tavily-search --from-existing
unset TAVILY_API_KEY
```

The profile allows POST only to `/search` and `/extract`; unrelated paths and
methods are not granted. Do not put the key value in documentation, TOML,
policy YAML, image layers, or shell scripts. Attach the instance alongside the
agent's inference provider only for sessions that need web research:

```bash
./run-exoshell-agent.sh --policy policies/policy.yaml --agent codex \
  --provider exoshell-codex --provider exoshell-tavily-search \
  . -- exec 'reply with OK'
```

CLI provider options replace the configured list, so include every instance
needed for that launch.

Smoke test inside a sandbox that attaches `exoshell-tavily-search` (the
output must not contain the readable key):

```bash
# inside the sandbox
curl --fail --silent --show-error https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d '{"query":"OpenShell sandbox providers","max_results":1}'
```
