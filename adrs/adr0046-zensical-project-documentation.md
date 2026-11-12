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
mode on pull requests and publish a Pages artifact from `main`. Only the deploy
job will receive Pages and OIDC write permissions.

## Consequences

- Users get a short setup path and focused guides without duplicated setup docs.
- Contributors can preview the site locally and review build failures in CI.
- GitHub Pages must use GitHub Actions as its publishing source.
- Existing file URLs retain pointers, but historical section bookmarks into the
  old monolithic guides may need updating.
- Zensical upgrades require checking the build and rendered navigation.

## References

- [Zensical publishing](https://zensical.org/docs/publish-your-site/)
- [Material maintenance status](https://squidfunk.github.io/mkdocs-material/)
- [Site configuration](../zensical.toml)
- [Documentation workflow](../.github/workflows/docs.yaml)
