# `install-agents`

## Purpose

Install one or more configured agent runtimes into one or more VMs.

## Commands

```bash
agsekit install-agents <agent_name> [<vm>|--all-vms] [--config <path>] [--proxychains <value>] [--debug]
agsekit install-agents --all-agents [--all-vms] [--config <path>] [--proxychains <value>] [--debug]
```

## Resolution Rules

- If `<vm>` is omitted, `agsekit` uses the agent target defined in config.
- If the agent has no VM restriction, all configured VMs become targets.
- With `--all-vms`, all configured VMs are targeted explicitly.

## Proxy Override

- `--proxychains scheme://host:port` overrides the VM proxy for this install.
- `--proxychains ""` disables proxying for one run.

## Examples

```bash
agsekit install-agents qwen
agsekit install-agents qwen agent-ubuntu
agsekit install-agents --all-agents --all-vms
agsekit install-agents claude --debug
```

## See Also

- [Supported agents](../agents.md)
- [run](run.md)
- [Networking](../networking.md)
