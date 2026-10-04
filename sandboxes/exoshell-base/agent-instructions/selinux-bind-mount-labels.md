# SELinux bind-mount file access

If a file under `/workspace` shows `Permission denied` or cannot be stat'ed,
especially after the user downloaded, moved, or renamed it on the host while
the sandbox was running, suspect an SELinux label mismatch. The host-created
file may retain `user_home_t` while the mounted project uses
`container_file_t`.

Tell the user to run this on the host, from the project directory:

```bash
chcon --reference=. path/to/file
```

Do not suggest `chmod` or `chown` as the fix, and do not claim that a command
run inside the sandbox can relabel the host file. If the cause is uncertain,
ask the user to compare host-side `ls -ldZ .` and `ls -lZ path/to/file` output.
