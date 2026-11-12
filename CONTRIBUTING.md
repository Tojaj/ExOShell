# Contributing to ExOShell

## Local checks

Use Git and Python 3.11 or newer with `venv` and pip support. From the
repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
pre-commit run --all-files --show-diff-on-failure
pre-commit run gitleaks-checkout --all-files --hook-stage manual
```

Checks are configured in [`.pre-commit-config.yaml`](.pre-commit-config.yaml).
The first run downloads tools. Some hooks modify files; review the changes and
rerun until all checks pass. Keep the virtual environment active so actionlint
can find ShellCheck when checking workflow scripts.

The manual Gitleaks check scans the working tree, including untracked files;
the commit hook checks staged changes.

Optionally install the commit hooks with `pre-commit install`.

## Tests

Tests assume a Unix environment with Bash, `jq`, and `openssl`; startup tests
also need a writable `/workspace`. With the virtual environment active, run
both suites outside pre-commit:

```bash
python scripts/run-unit-tests.py --allow-missing-clients tests
python scripts/run-unit-tests.py .agents/skills/bump-exoshell-base-versions/tests
```

`--allow-missing-clients` permits selected installed-agent tests to skip when
their required clients are unavailable. Omit it to require zero skips.

See the [CI workflow](.github/workflows/ci.yaml) for hosted checks and
[ADR-0045](adrs/adr0045-unprivileged-first-phase-ci.md) for CI design decisions.

## Documentation

User guides live in `docs/`; edit them there rather than duplicating setup in
the README or the legacy provider/customization entry points. Keep the
specification and ADRs in the repository. Use relative links within `docs/`
and full GitHub links for source files outside it.

With a virtual environment active:

```bash
python -m pip install -r requirements-docs.txt
zensical serve
# Production validation (also runs on documentation pull requests):
zensical build --clean --strict
```

Open the local URL printed by `zensical serve`. Check light/dark mode, narrow
screens, navigation, search, and code tabs when changing layout. Generated
`site/` and `.cache/` content is ignored. Navigation is in `zensical.toml`;
local page labels match their H1 headings, except the homepage's "Overview".

The [Documentation workflow](.github/workflows/docs.yaml) validates pull
requests and publishes pushes to `main` at <https://tojaj.github.io/ExOShell/>.
Automatic runs are limited to changes in `docs/**`, `zensical.toml`,
`requirements-docs.txt`, or the documentation workflow itself. General CI
still runs on every pull request. Manual documentation runs remain available.
For the initial publication, select **Settings → Pages → Build and deployment
→ Source → GitHub Actions** in the GitHub repository, then run the workflow on
`main` (or push a matching change). Forks must update `site_url` and repository links
before publishing to their own Pages site. No custom domain is required.

### Dependency updates

Keep Zensical pinned in `requirements-docs.txt`. Once
[the Dependabot configuration](.github/dependabot.yml) reaches the default
branch, Dependabot checks monthly for Zensical updates and opens at most one
version-update PR at a time. A seven-day release cooldown satisfies the
repository's security lint. Only Zensical is included; development dependencies,
pre-commit hooks, and GitHub Actions are outside this update configuration.

Updates require manual review and merging. Require a successful strict build
and preview the site with the proposed version before merging, including
navigation, search, light/dark mode, narrow screens, and code tabs.

## Commit messages

- Use clear, descriptive commit messages following Conventional Commits, with
  a type such as `feat`, `fix`, `docs`, or `chore` and an optional scope such as
  `policy`, `provider`, or `runner`.
- Use imperative mood: "fix" rather than "fixes".
- Keep the body concise: explain the motivation and reasoning; the diff shows
  what changed. Call out non-obvious consequences for reviewers.
- Separate the title and body with a blank line and wrap body lines at 75 columns.
