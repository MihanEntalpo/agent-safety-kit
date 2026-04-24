# Known Issues

This page collects current limitations.

## Contents

- [Current Limitations](#current-limitations)
- [Operational Notes](#operational-notes)

## Current Limitations

- There are problems with mounting folders whose paths contain non-ASCII characters; this is a Multipass issue.
- There are problems with mounting folders whose paths contain hidden names; this is also a Multipass issue.
- If you work with several users on one PC, you need to have roughly the same agsekit configuration, otherwise various problems are possible.
- If you work with several users on one PC, there will be no isolation between users, because Multipass and its VMs are global for the whole machine, not per user.
- VM size cannot yet be changed automatically after changing its size in the configuration. If needed, do this with Multipass tools.
- WSL is not supported; use a regular Linux host or native Windows PowerShell.
- Large installers and source builds can be slow on small VMs.
- `agsekit run <agent>` itself may not be very fast because of preparation steps and backups.
- `agsekit daemon` is not implemented yet on Windows; run needed background commands manually in a separate terminal there.

## Operational Notes

- specific proxy settings depend on the capabilities of the agent CLI itself (for example, claude-code does not work with proxychains)
- backup policy protects files, but does not protect from external side effects such as DB changes or network actions
- if several folders are mounted into one VM, then by running an agent in one of them, you still risk the others, although this risk is much smaller than when running on the host.

## See Also

- [Troubleshooting](troubleshooting.md)
- [Project philosophy](philosophy.md)
