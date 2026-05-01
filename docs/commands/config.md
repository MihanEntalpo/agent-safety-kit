# `config-example` / `config-gen`

These commands help you create an `agsekit` YAML config.

## `agsekit config-example [destination]`

Copies the bundled example config to a target path.

- Default destination: `~/.config/agsekit/config.yaml`
- If the default file already exists, the command leaves it unchanged
- Useful when you want to edit YAML manually from a known starting point

## `agsekit config-gen [--config <path>] [--overwrite]`

Runs an interactive config wizard and writes the result as YAML.

Important behavior:

- The first VM is always mandatory
- Additional VMs are optional
- Agents are optional
- Mounts are optional
- Global overrides are optional and are asked only at the end

Wizard flow:

1. Configure the first VM: name, CPU, RAM, disk, install bundles, optional proxy settings, optional port-forwarding.
2. Optionally add more VMs.
3. Configure agents:
   - choose an agent type from a TUI list
   - choose a name
   - optionally add `env`
   - optionally add `default-args`
   - when more than one VM exists, assign the agent to one or more VMs
   - optionally override `proxychains` and `http_proxy`
4. Optionally configure mounts:
   - `source`
   - `target`
   - `backup`
   - target VM
   - optional allowed-agent restrictions
   - optional default `.backupignore`
5. Optionally override global settings.
6. Choose the destination path and save the YAML.

Notes:

- Install bundles are chosen with checkboxes and may be left empty.
- Port-forwarding rules can be added one by one; after each rule the wizard asks whether you want to add another one for the same VM.
- VM names must be unique within one wizard run. The wizard starts from `agent-ubuntu` and then proposes `agent-ubuntu-2`, `agent-ubuntu-3`, and so on when needed.
- Agent names must also be unique. If the default binary-based name is already used, the wizard proposes `name-2`, `name-3`, and so on.
- Agent `default-args` are stored as a YAML list split by spaces.
- Entering literal `""` for an agent proxy override writes an explicit empty string to YAML; pressing Enter leaves the value inherited.
- When an agent is assigned to specific VMs, the wizard also fills `vms.<name>.allowed_agents` so those VM restrictions stay consistent with the agent assignments.
- Without `--overwrite`, the command does not replace an existing file.

## See Also

- [Getting started](../getting-started.md)
- [Configuration](../configuration.md)
