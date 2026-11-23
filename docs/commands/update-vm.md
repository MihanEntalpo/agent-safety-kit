# `update-vm`

Apply CPU and RAM from the configuration to one existing Multipass VM or all configured VMs.

```bash
agsekit update-vm <vm_name>|--all-vms [-f|--force] [--config <path>] [--debug]
```

A stopped VM is updated directly through the Multipass `local.<vm>.cpus` and `local.<vm>.memory` settings. If a VM is running, the command shows configured agent processes and asks before stopping it; the default answer is No. With `--force`, it stops, updates, and starts running VMs without a prompt, which is suitable for automation.

Suspended VMs are skipped. Resume them first with `multipass start <vm_name>`. The command changes only CPU and RAM; disk differences are not modified.

See also: [VM lifecycle](vm-lifecycle.md), [up](up.md).
