# Search tools in this image

When searching from the shell, prefer `rg` for text, `fd` for files and
directories, and `ast-grep` for syntax-aware code searches. This image provides
`fd` as a command for Debian's `fdfind`.

Use other tools when their behavior is needed. In particular, `rg` and `fd`
skip hidden and ignored files by default; include those files explicitly when
the task requires them.
