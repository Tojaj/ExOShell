---
status: accepted
date: 2026-11-12
topics:
  - documentation
  - ci
---

# 46. Publish task-focused documentation with Zensical

## Context

The README, provider guide, and customization guide contain useful detail but
are too long to serve as an introduction. A GitHub Pages site needs navigation,
search, and a short path to a first session. Material for MkDocs is in
maintenance mode, with end of life announced for May 5, 2027. Zensical is its
successor and supports Markdown and GitHub Actions publishing.

## Decision

We will use Zensical with a pinned version and make `docs/` the canonical source
for user guides. The README will introduce the project and link to the guides;
the old provider and customization paths will retain navigation pointers.
The specification, implementation architecture notes, and ADRs will remain in
the repository and be linked from the site.

We will use the built-in theme, search, code tabs, and Mermaid support with
minimal styling for existing branding. A separate workflow will build in strict
mode on pull requests and publish a Pages artifact from `main`. Automatic runs
will be limited to changes under `docs/`, the Zensical configuration, the docs
requirements, or the documentation workflow itself; manual runs will remain
available. Only the deploy job will receive Pages and OIDC write permissions.

We will configure Dependabot to check monthly for updates to the pinned
Zensical dependency only, with at most one version-update PR open at a time
and a seven-day release cooldown as required by the repository's security lint.
Updates will require manual review and merging after a strict build and visual
preview. Navigation labels will match local page H1 headings, except for the
homepage's "Overview" label.

## Consequences

- Users get a short setup path and focused guides without duplicated setup docs.
- Contributors can preview the site locally and review build failures in CI.
- Unrelated code changes will not rebuild or redeploy the site; general CI
  will continue running on every pull request.
- GitHub Pages must use GitHub Actions as its publishing source.
- Existing file URLs retain pointers, but historical section bookmarks into the
  old monolithic guides may need updating.
- Zensical upgrades require checking the build and rendered navigation.
- Monthly update checks will begin when the Dependabot configuration reaches
  the default branch; other dependencies will remain outside this automation.

## References

- [Zensical publishing](https://zensical.org/docs/publish-your-site/)
- [Material maintenance status](https://squidfunk.github.io/mkdocs-material/)
- [Site configuration](../zensical.toml)
- [Documentation workflow](../.github/workflows/docs.yaml)
- [Dependabot configuration](../.github/dependabot.yml)
- [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
