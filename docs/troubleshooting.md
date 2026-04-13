# Troubleshooting

This page collects the most typical operational problems.

## Empty Mounted Folders

* Folders are mounted
* But they are empty inside
* When trying to mount, both agsekit and Multipass say "everything is already mounted"
* When trying to unmount, an sshfs server error occurs

`agsekit doctor` can detect and fix such problems.

Usually, restarting the Multipass daemon is enough.

## See Also

- [Known issues](known-issues.md)
- [doctor](commands/doctor.md)
- [Networking](networking.md)
