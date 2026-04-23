# `install-agents`

## Contents

- [Purpose](#purpose)
- [Commands](#commands)
- [Target Selection Rules](#target-selection-rules)
- [Proxychains Override](#proxychains-override)
- [Examples](#examples)

## Purpose

Install one or more configured agent runtimes into one or more VMs.

Before running the installer playbook, `agsekit` makes sure the VM contains the host SSH key. The key bootstrap is done through Multipass, and the installer itself runs through Ansible over SSH using `global.ssh_keys_folder`.

## Commands

```bash
agsekit install-agents <agent_name> [<vm>|--all-vms] [--config <path>] [--proxychains <value>] [--debug]
agsekit install-agents --all-agents [--all-vms] [--config <path>] [--proxychains <value>] [--debug]
```

## Target Selection Rules

- If `<vm>` is not passed, `agsekit` uses the target VM of the agent from the config.
- If the agent has no VM restrictions, all VMs from the config become targets.
- With `--all-vms`, all VMs are selected explicitly.

## Proxychains Override

By default, install-agents uses proxychains from the VM configuration, which can be overridden at launch:

- `--proxychains scheme://host:port` overrides the VM proxy only for this installation.
- `--proxychains ""` disables proxy for one run.

For Node-based agents (`codex`, `qwen`, `opencode`, `cline`), if `node` is missing, the installer resolves the latest available patch release inside the supported Node 24 major line through `nvm ls-remote` and installs that exact version.

For the same Node-based agents, the installer checks for an existing Node.js both in the current `PATH` and through `nvm use --silent default`, so a Node version that is already installed through `nvm` does not trigger a redundant reinstall just because Ansible is running in a non-login shell.

For `codex`, `codex-glibc`, and `codex-glibc-prebuilt`, the installer also configures `logrotate` inside the VM for `~/.codex/log/codex-tui.log` with `size 100M`, `rotate 10`, `compress`, `delaycompress`, `missingok`, `notifempty`, and `copytruncate`.

## Examples

```bash
agsekit install-agents qwen
agsekit install-agents qwen agent-ubuntu
agsekit install-agents --all-agents --all-vms
agsekit install-agents claude --debug
```

## See Also

- [Agents](../agents.md)
- [run](run.md)
- [Networking](../networking.md)
