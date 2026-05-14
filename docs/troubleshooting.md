# Troubleshooting

This page collects the most typical operational problems.

## Empty Mounted Folders

* Folders are mounted
* But they are empty inside
* When trying to mount, both agsekit and Multipass say "everything is already mounted"
* When trying to unmount, an sshfs server error occurs

`agsekit doctor` can detect and fix such problems.

Usually, restarting the Multipass daemon is enough.

## Multiple Node.js Versions With Agents

If different Node-based agents were installed into different `nvm` Node.js versions inside the same VM, `agsekit doctor` can consolidate them:

* it keeps the newest Node.js version that already has agents;
* removes the other agent-bearing Node.js versions;
* reinstalls only the configured agents that were actually detected in that VM;
* leaves Node.js versions without agents untouched.

## See Also

- [Known issues](known-issues.md)
- [doctor](commands/doctor.md)
- [Networking](networking.md)
