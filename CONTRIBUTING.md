# Contributing to ExOShell

## Local checks

Use Python 3.11 or newer, plus Git, `jq`, and `openssl`. CI tests the minimum
supported Python version, 3.11. From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
pre-commit run --all-files --show-diff-on-failure
```

Pre-commit installs its pinned tools into isolated environments. The first run
needs network access to obtain them. Hooks clean whitespace and final newlines,
validate YAML/JSON/TOML (including `.exoshell.local.toml.example`), lint and
format Python with Ruff, check shell scripts with ShellCheck, and check Actions
with actionlint and offline zizmor in its auditor persona. Findings fail the
check. Review automatic edits and rerun until every hook passes. Ruff includes
the extensionless `sandboxes/exoshell-base/exoshell-agent` helper and targets
Python 3.11 with its default lint rules and the narrowly documented exceptions
in `ruff.toml`.

To run just Python linting and formatting:

```bash
pre-commit run ruff-check --all-files
pre-commit run ruff-format --all-files
```

Optionally install the Git hook with `pre-commit install`. The planning checkout
had `core.hooksPath=/dev/null`, which disables hooks and prevents installation.
Check `git config --show-origin --get core.hooksPath` and choose whether to change
that setting yourself; the setup above does not alter it. Explicit
`pre-commit run` commands work with hooks disabled.

## Tests

Run the two suites separately, outside pre-commit:

```bash
python scripts/run-unit-tests.py --allow-missing-clients tests
python scripts/run-unit-tests.py .agents/skills/bump-exoshell-base-versions/tests
```

The runner fails on test failures, errors, empty suites, and unexpected skips.
Host runs may skip only the five installed-agent tests named in
`scripts/run-unit-tests.py`, and only for their listed missing-client reasons
(including OpenCode v1 where v2 is required). Review any allowlist change
explicitly. Omit `--allow-missing-clients` to require zero skips in an image
containing all agents.

Startup tests need a writable `/workspace`. On a disposable Linux test host,
create it if absent with `sudo install -d -o "$(id -u)" -g "$(id -g)" -m 0755
/workspace`. All other missing prerequisites cause CI to fail. The direct
`python -m unittest discover -s tests -v` command remains useful for debugging,
but does not enforce skip policy; the skill suite uses discovery directory
`.agents/skills/bump-exoshell-base-versions/tests`.

## CI rollout and maintenance

The workflow checks every PR targeting `main`, every push to `main`, and manual
dispatches, including documentation-only changes. The parallel `pre-commit`
and `unit-tests` jobs feed the aggregate check named **CI**. It succeeds only
when both jobs succeed, including after dependency failures or cancellations.
See [ADR-0045](adrs/adr0045-unprivileged-first-phase-ci.md) for the security
boundaries.

After the first hosted runs, a repository administrator should select **CI**
as a required status check in the rule protecting `main`. Confirm fork PR
validation, documentation-only completion, the expected missing-client skips,
and aggregate failure behavior before requiring it. Repository settings are
a separate rollout step.

Review workflow, hook configuration, tool versions, and skip-allowlist changes
as executable CI changes. Keep Actions and hook repositories pinned to verified
full commit SHAs with release comments, and Python tool dependencies pinned to
exact versions. Verify replacement pins against upstream tags/source and rerun
all checks. Image builds, registry publication, and Pages deployment are deferred.

## Commit messages

- Use clear and descriptive and commit messages.
- Follow Conventional Commits spec - i.e. Prefix title type such as feat, fix,
  docs, chore, .. and if applicable also scope - e.g. `policy`, `provider`, `runner`, ..
- Use imperative mood: "fix .." not "fixes ..".
- Concise body must focus on why, not what. The "what" is visible in the diff.
- The message should explain the motivation, the reasoning, or what problem is being solved.
- Call out consequences of the change that are non-obvious and anything important
  reviewer should know.
- Body has lines wrapped at 75 columns.
- Insert an empty line between title (first line) and body.
