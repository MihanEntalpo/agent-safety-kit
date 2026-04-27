# Backups

Backups are a core part of the `agsekit` workflow.

## Contents

- [Model](#model)
- [Main Commands](#main-commands)
- [During `agsekit run`](#during-agsekit-run)
- [Cleanup Policies](#cleanup-policies)
- [`.backupignore`](#backupignore)

## Model

- Snapshots are created on the host side.
- Data is copied through `rsync`.
- Unchanged files are hardlinked from the previous snapshot.
- A single destination directory is protected by a file lock, so only one backup writer writes to it.
  - This way, if 2 or more agents are running in the same folder, backups are made only once, not N times more often.
- If nothing changed between the last backup and the current folder state, no backup is created.
  - As a result, an agent you forgot about will not create 100 identical backups.

## Main Commands

More details about commands here: [Backup commands](commands/backups.md)

- `backup-once`
- `backup-repeated`
- `backup-repeated-mount`
- `backup-repeated-all`
- `backup-clean`

## During `agsekit run`

If backups are enabled for the selected mount and `--disable-backups` was not passed:

1. `agsekit` makes sure an initial snapshot exists, and by default also makes a blocking pre-run snapshot when snapshots already exist;
2. the agent starts inside the VM;
3. repeated backups keep running in the background for the whole session.

The effective pre-run backup policy is resolved like this:

1. `--first-backup` forces the blocking pre-run snapshot.
2. `--no-first-backup` disables it when snapshots already exist.
3. If no CLI override was passed, `mounts[].first_backup` is used.
4. If the backup chain does not exist yet, the initial snapshot is still created regardless.

If `--disable-backups` is passed, background repeated backups are not started, but the initial/pre-run snapshot can still run according to the rules above.

If `agsekit run` is started either from a missing project folder or from an existing folder outside configured mounts, and the user agrees to a temporary workdir inside the VM, no mount is selected and backups are not started for that session.

## Cleanup Policies

- `tail`: keep the last N snapshots
- `thin`: logarithmic thinning: dense history near the current time and increasingly sparse older snapshots

## `.backupignore`

`agsekit` reads `.backupignore` inside the source tree and passes exclusion logic to `rsync`.

Example .backupignore:

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
