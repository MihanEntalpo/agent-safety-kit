# Known Issues

This page tracks current limitations rather than bugs already fixed.

## Current Limitations

- Windows host support is not a first-class workflow yet.
- Linux-only `systemd` integration does not currently have a native macOS `launchd` replacement.
- Guest isolation is helpful, but mounted folders are still writable by the guest VM.
- Large agent installers and source builds can be slow on small VMs.

## Operational Caveats

- Multipass mount behavior can fail independently of `agsekit`.
- Network proxy configuration is agent-dependent beyond the generic runtime wrappers.
- Backup policy protects files, not external side effects such as database changes or network actions.

## See Also

- [Troubleshooting](troubleshooting.md)
- [Project philosophy](../philosophy.md)
