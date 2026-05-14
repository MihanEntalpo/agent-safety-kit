# `doctor`

## Contents

- [Purpose](#purpose)
- [Command](#command)
- [Current Scope](#current-scope)
- [Behavior](#behavior)
- [Examples](#examples)

## Purpose

Diagnose known installation and runtime problems and suggest safe fixes.

## Command

```bash
agsekit doctor [--config <path>] [-y] [--debug]
```

## Current Scope

The command currently covers two repairable issue classes:

- broken Multipass mount visibility, when a non-empty host folder looks empty inside the VM;
- scattered Node-based agents across multiple `nvm` Node.js versions in the same VM.

## Behavior

- analyzes configured mounts;
- checks whether a non-empty host directory looks empty inside the VM;
- checks `~/.nvm/versions/node/*` inside running VMs and looks for Node-based agents (`codex`, `qwen`, `opencode`, `cline`) inside each version;
- if several `nvm` Node.js versions contain agents, offers to keep the newest such version as default, remove the other agent-bearing versions, and reinstall only the agent names from the config that were actually detected in that VM;
- Node.js versions without detected agents are left untouched;
- for broken mounts, can suggest restarting the Multipass daemon.

## Examples

Run in interactive mode:

```bash
agsekit doctor
```

Run and agree to apply fixes:

```shell
agsekit doctor -y
```

Run with detailed diagnostic output:

```shell
agsekit doctor --debug
```

## See Also

- [Troubleshooting](../troubleshooting.md)
- [create-vm](create-vm.md)
