# ADRs in this repo

Architecture Decision Records document the *why* behind non-obvious choices in
the OpenShell configuration — especially choices that constrain or couple
multiple files. Without an ADR, a future reader might unknowingly revert a
deliberate decision.

[ADR pattern](http://thinkrelevance.com/blog/2011/11/15/documenting-architecture-decisions)

## File naming

`adrNNNN-kebab-description.md` — four-digit zero-padded number, lowercase
hyphenated description.

Examples: `adr0001-graphql-endpoint-declared-once-in-user-policy.md`

## Template

`adrs/adr000-adr-template.md` is the starting point.

## Authoring guidance

### Structure

```markdown
---
status: proposed
date: YYYY-MM-DD
# author: Firstname Lastname
topics:
  - topic-tag
---

# N. Title of the Decision

## Context

[Neutral description of the problem and forces at play. If multiple options
were considered, enumerate them with trade-offs before the decision.]

## Decision

[Active voice: "We will..." or "X will be...". Advocates for the chosen path.]

## Consequences

[All resulting impacts: positive, negative, and neutral. May be a flat bullet
list or structured subsections (### Positive / ### Negative / ### Mitigations).]

## References

- [Related file or doc](path/or/url)
```

Use YAML frontmatter for metadata, following the [MADR template](https://github.com/adr/madr/blob/main/template/adr-template.md).
Keep `status`, `date`, and at least one `topics` entry in every ADR. Topics are
lowercase, hyphenated names; reuse existing topics when they fit. Add `author`
only when known; it names the record's writer, not necessarily every decision
maker. The date is the recorded decision date; do not change it during
metadata-only edits. A superseded ADR also gets `superseded-by` with the
replacement ADR's relative file path, plus a Markdown link in the body for
readers.

**Author** and **References** are optional but encouraged.

### Status lifecycle

| Status | Meaning |
|--------|---------|
| `proposed` | Under discussion |
| `accepted` | In effect |
| `deprecated` | No longer relevant, kept for history |
| `superseded` | A newer ADR replaces this one; set `superseded-by` |

When superseding, update the old ADR's `status` and `superseded-by`, link to
the replacement in its body, and reference the old ADR in the new ADR's Context.

### Numbering

Scan `adrs/` for the highest `adrNNNN` number and increment. Never reuse a
number.

### Cross-referencing

Use relative links: `[ADR-0001](adr0001-graphql-endpoint-declared-once-in-user-policy.md)`

### What NOT to do

- Do not skip the Context section — it is the most valuable part.
- Do not write Context as advocacy — save advocacy for Decision.
- Do not use present tense in Decision ("We use...") — write "We will..." or
  "We decided to...".
