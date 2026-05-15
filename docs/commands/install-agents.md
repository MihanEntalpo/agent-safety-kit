# `install-agents`

## Contents

- [Purpose](#purpose)
- [Commands](#commands)
- [Target Selection Rules](#target-selection-rules)
- [Proxychains Override](#proxychains-override)
- [Examples](#examples)

## Purpose

Install one or more configured agent runtimes into one or more VMs.

Before running the installer playbook, `agsekit` makes sure the VM contains the host SSH key. The key bootstrap is done through Multipass. On Linux and macOS the installer itself runs through Ansible over SSH using `global.ssh_keys_folder`; on native Windows PowerShell it runs inside the target VM against `localhost` through a VM-local control node.

Agent versions come from `agents.<name>.version`. If the field is omitted, `agsekit` installs the pinned default version for that agent type.

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

## Examples

```bash
agsekit install-agents qwen
agsekit install-agents qwen agent-ubuntu
agsekit install-agents --all-agents --all-vms
agsekit install-agents claude --debug
```

## Notes

Before running a playbook, `agsekit` asks an existing agent binary for its version. If it already matches the requested version, the install step is skipped. If the binary exists but the version differs, `agsekit` reinstalls that agent to reach the version declared in the config.

For Node-based agents (`codex`, `qwen`, `opencode`, `claude`, `cline`), if `node` is missing, the installer resolves the current Node.js LTS through `nvm version-remote --lts` and installs that exact version. If Node.js is already present, the installer keeps the existing version and does not auto-upgrade it just because a newer LTS appeared.

For the same Node-based agents, the installer checks for an existing Node.js both in the current `PATH` and through `nvm use --silent default`, so a Node version that is already installed through `nvm` does not trigger a redundant reinstall just because Ansible is running in a non-login shell. When multiple Node-based agents are installed into the same VM in one `install-agents` run, `agsekit` remembers after the first successful installer that `nvm` and Node.js are already ready in that VM and passes flags to later installer playbooks so they skip repeated `nvm`/Node preparation.

For `codex-glibc-prebuilt`, agsekit resolves the exact GitHub release tag that corresponds to the requested version. For `codex-glibc`, it clones the exact matching Git tag before building.

If the requested version does not exist upstream, installation fails explicitly instead of silently falling back to `latest`.

For `codex`, `codex-glibc`, and `codex-glibc-prebuilt`, the installer also configures `logrotate` inside the VM for `~/.codex/log/codex-tui.log` with `size 100M`, `rotate 10`, `compress`, `delaycompress`, `missingok`, `notifempty`, and `copytruncate`.


## See Also

- [Agents](../agents.md)
- [run](run.md)
- [Networking](../networking.md)
