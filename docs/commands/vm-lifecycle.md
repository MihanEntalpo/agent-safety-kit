# VM Lifecycle Commands

## Covered Commands

```bash
agsekit start-vm <vm_name>|--all-vms [--config <path>] [--debug]
agsekit stop-vm <vm_name>|--all-vms [--config <path>] [--debug]
agsekit restart-vm <vm_name>|--all-vms [--config <path>] [--debug]
agsekit down [--config <path>] [-f|--force] [--debug]
agsekit destroy-vm <vm_name>|--all [--config <path>] [-y] [--debug]
```

## `start-vm`

Starts the selected VM or all configured VMs.

## `stop-vm`

Stops the selected VM or all configured VMs. Existing mounts are unmounted first when required by the implementation.

## `restart-vm`

Runs the stop/start sequence for the selected targets.

## `down`

Stops all configured VMs. If configured agents are still running, `agsekit` shows them and asks for confirmation unless `--force` is used.

On Linux, `down` also attempts to stop the `portforward` systemd service first.

## `destroy-vm`

Deletes the VM from Multipass after confirmation.

## See Also

- [create-vm](create-vm.md)
- [status](status.md)
