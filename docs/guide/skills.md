# User skills

Select skill sources with the common `skills` list. Nothing is imported by
default. Each path can be an individual skill directory containing `SKILL.md`
or a collection whose immediate children are skill directories:

```toml
skills = ["~/.agents/skills", "../shared-skills", "../tools/example-skill"]
```

Paths expand `~` and resolve relative to the selected configuration file.
Repeatable `--skill PATH` options replace the configured list for one launch
and resolve relative to the caller. `--no-skills` ignores configured sources:

```bash
./run-exoshell-agent.sh --skill ~/shared-skills --skill ./example-skill
./run-exoshell-agent.sh --no-skills
```

The launcher snapshots complete skill directories, following symlinks and
preserving executable scripts. Symlink aliases retain their directory names.
Collection files and unrelated directories are ignored; discovery does not
recurse into nested collections. Missing paths, unreadable content, broken
links, cycles, and special files fail before provisioning.

Duplicate names among configured skills fail before provisioning. Any name
already present in the image also fails before the agent starts; nothing
overwrites image skills. Select individual skills when a home collection
includes copies of skills already provided by the image.

The snapshot is temporarily mounted read-only at `/tmp/exoshell-skills`, then
copied into `/sandbox/.agents/skills`. Source changes after the snapshot do not
propagate, and sandbox edits do not update host skills. Host staging is removed
after the launcher returns; `--keep` retains container copies. `--no-share`
still imports explicitly configured skills and permits this snapshot mount,
while suppressing project and kubeconfig mounts.

Rebuild the base and dependent images to enable imports. Claude's
`/sandbox/.claude/skills` is a directory symlink to `../.agents/skills`, so both
image and imported skills are visible through the same directory. Custom
policies must allow reading `/tmp/exoshell-skills` and reading/writing the real
`/sandbox/.agents/skills` directory; the baseline already does. The snapshot
uses the same local gateway filesystem requirement as existing project mounts.
See [ADR-0038](https://github.com/Tojaj/ExOShell/blob/main/adrs/adr0038-user-skill-snapshots.md).
