# Backups

Backups are a core part of the `agsekit` workflow.

## Model

- Snapshots are created on the host.
- Data is copied with `rsync`.
- Unchanged files are hardlinked from the previous snapshot.
- One destination directory is protected by a filesystem lock, so only one backup writer works there at a time.
- Progress rsync flags are host-platform aware: Linux uses `--progress --info=progress2`, while macOS and Windows use `--progress` for compatibility with older rsync builds.

## Main Commands

- `backup-once`
- `backup-repeated`
- `backup-repeated-mount`
- `backup-repeated-all`
- `backup-clean`

## During `agsekit run`

If the chosen mount has backups enabled and `--disable-backups` is not used:

1. `agsekit` ensures an initial snapshot exists;
2. the agent starts inside the VM;
3. repeated backups continue in the background for the duration of the session.

If `agsekit run` is started from a missing project folder and the user accepts the temporary VM workdir prompt, no mount is selected and backups are not started for that session.

## Cleanup Policies

- `tail`: keep the newest N snapshots
- `thin`: keep dense recent history and increasingly sparse older history

## `.backupignore`

`agsekit` reads `.backupignore` files inside the source tree and forwards exclusion logic to `rsync`.

Example:

```text
venv/
node_modules/
*.log
!logs/important.log
```

## See Also

- [Backup commands](commands/backups.md)
- [Troubleshooting](troubleshooting.md)
- [Architecture](architecture.md)
